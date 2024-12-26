import logging

from locust.exception import StopUser

import vsb
from vsb import logger
import vecs
from vecs import IndexMeasure, Collection
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, after_log
import grpc.experimental.gevent as grpc_gevent
import time

from ..base import DB, Namespace
from ...vsb_types import Record, SearchRequest, DistanceMetric, RecordList

# patch grpc so that it uses gevent instead of asyncio. This is required to
# allow the multiple coroutines used by locust to run concurrently. Without it
# (using default asyncio) will block the whole Locust/Python process,
# in practice limiting to running a single User per worker process.
grpc_gevent.init_gevent()

class SupabaseNamespace(Namespace):
    def __init__(self, index: Collection, namespace: str, index_measure: IndexMeasure):
        # TODO: Support multiple namespaces
        self.index = index
        self.index_measure = index_measure

    def insert_batch(self, batch: RecordList):
        # Convert RecordList to list of tuples (id, values, metadata) for Supabase
        records = [(record.id, record.values, record.metadata) for record in batch]
        self.index.upsert(
            skip_adapter=True, 
            records=records
            )

    def update_batch(self, batch: list[Record]):
        # Supabase treats insert and update as the same operation.
        self.insert_batch(batch)

    def search(self, request: SearchRequest) -> list[str]:
        @retry(
            wait=wait_exponential_jitter(initial=0.1, jitter=0.1),
            stop=stop_after_attempt(5),
            after=after_log(logger, logging.DEBUG),
        )
        def do_query_with_retry():
            return self.index.query(
                data=request.values,
                limit=request.top_k,
                filters=request.filter,
                measure=self.index_measure
            )

        result = do_query_with_retry()
        matches = [id for id in result]  # List of ids
        return matches

    def fetch_batch(self, request: list[str]) -> list[Record]:
        # vecs Record is Tuple[str, Iterable[Numeric], Metadata]
        # VSB Record needs id: str, values: Vector, metadata: dict
        result = self.index.fetch(ids=request)
        return [
            Record(
                id=record[0],  # id is first element
                values=list(record[1]),  # values is second element, convert Iterable to list
                metadata=record[2] if record[2] else None  # metadata is third element
            ) for record in result
        ]

    def delete_batch(self, request: list[str]):
        self.index.delete(ids=request)
 

class SupabaseDB(DB):
    def __init__(
        self,
        record_count: int,
        dimensions: int,
        metric: DistanceMetric,
        name: str,
        config: dict,
    ) -> None:
        self.skip_populate = config["skip_populate"]
        self.overwrite = config["overwrite"]
        # We will use the name of the workload as the namespace for the index
        self.name = f"vsb-{name}"
        self.dimensions = dimensions
        self.metric = metric

        # create vector store client, connecting to Supabase
        self.vx = vecs.create_client(config["supabase_connection_string"])

        try:
            self.index = self.vx.get_or_create_collection(
                name=self.name, 
                dimension=dimensions
                )
        except Exception as e:
            logger.info(
                "SupabaseDB: Failed to create index with provided credentials "
                "or dimensions do not match. Check Supabase Dashboard for details. "
                f"Error: {e}"
            )
            raise StopUser()

        measure = SupabaseDB._get_distance_func(metric)
        self.measure = measure

    @staticmethod
    def _get_distance_func(metric: DistanceMetric) -> IndexMeasure:
        match metric:
            case DistanceMetric.Cosine:
                return IndexMeasure.cosine_distance
            case DistanceMetric.Euclidean:
                return IndexMeasure.l2_distance
            case DistanceMetric.DotProduct:
                raise ValueError("SupabaseDB: DotProduct metric is not supported")

    def get_batch_size(self, sample_record: Record) -> int:
        # Copied from the PgvectorDB implementation
        return 1000

    def get_namespace(self, namespace: str) -> Namespace:
        return SupabaseNamespace(self.index, self.name, self.measure)

    def initialize_population(self):
        # If the index already existed before VSB (we didn't create it) and
        # user didn't specify skip_populate; require --overwrite before
        # deleting the existing index.
        if self.skip_populate:
            return
        if not self.overwrite:
            msg = (
                "SupabaseDB: Index already exists - cowardly refusing"
                " to overwrite existing data. Specify --overwrite to delete"
                " it, or specify --skip-populate to skip population phase."
            )
            logger.critical(msg)
            raise StopUser()
        try:
            logger.info(
                "SupabaseDB: Clearing existing index before "
                "population (--overwrite=True) "
            )
            logger.info(f"SupabaseDB: Index namespace: {self.name}")
            self.index._drop() # delete the collection
            # re-create the collection
            self.index = self.vx.get_or_create_collection(
                name=self.name, 
                dimension=self.dimensions
                )
        except Exception as e:
            # Serverless indexes can throw a "Namespace not found" exception for
            # delete_all if there are no documents in the index. Simply ignore,
            # as the post-condition is the same.
            logger.info(f"SupabaseDB: Error deleting index: {e}")
            pass

    def finalize_population(self, record_count: int):
        """Wait until all records are visible in the index"""
        logger.debug(f"SupabaseDB: Waiting for record count to reach {record_count}")
        with vsb.logging.progress_task(
            "  Finalize population", "  ✔ Finalize population", total=record_count
        ) as finalize_id:
            while True:
                index_count = self.index.__len__() # returns number of vectors in the collection
                if vsb.progress:
                    vsb.progress.update(finalize_id, completed=index_count)
                if index_count >= record_count:
                    logger.debug(
                        f"SupabaseDB: Index vector count reached {index_count}, "
                        f"finalize is complete"
                    )
                    break
                time.sleep(1)

        # index the collection for fast search performance
        self.index.create_index(measure = self.measure)

    def skip_refinalize(self):
        return False

    def get_record_count(self) -> int:
        return self.index.__len__()