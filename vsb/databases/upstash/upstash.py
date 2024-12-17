import logging

from locust.exception import StopUser

import vsb
from vsb import logger
from upstash_vector import AsyncIndex, Index, Vector
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

class UpstashNamespace(Namespace):
    def __init__(self, index: Index, namespace: str):
        self.index = index
        self.namespace = namespace

    def insert_batch(self, batch: RecordList):
        # Upstash expects a list of dicts (or tuples).
        # Upstash uses the term "vector" for the dense vector data
        # We need to rename the key to "values" for the RecordList
        dicts = []
        for record in batch:
            # Create a new dictionary with "vector" as the renamed key for "values"
            updated_record = {
                "vector": record.values,  # Rename "values" to "vector"
                "id": record.id,
                "metadata": record.metadata
            }
            dicts.append(updated_record)
        self.index.upsert(dicts, namespace=self.namespace)

    def update_batch(self, batch: list[Record]):
        # Upstash has an update function for single vector updates
        # For batch updates, upserting again is the correct practice
        self.insert_batch(batch)

    def search(self, request: SearchRequest) -> list[str]:
        @retry(
            wait=wait_exponential_jitter(initial=0.1, jitter=0.1),
            stop=stop_after_attempt(5),
            after=after_log(logger, logging.DEBUG),
        )
        def do_query_with_retry():
            return self.index.query(
                vector=request.values, 
                top_k=request.top_k, 
                filter=request.filter,
                namespace=self.namespace
            )

        query_result = do_query_with_retry()
        matches = [result.id for result in query_result]
        return matches

    def fetch_batch(self, request: list[str]) -> list[Record]:
        return self.index.fetch(
            ids=request, 
            include_vectors=True,
            include_metadata=True,
            namespace=self.namespace
            )

    def delete_batch(self, request: list[str]):
        self.index.delete(request)


class UpstashDB(DB):
    def __init__(
        self,
        record_count: int,
        dimensions: int,
        metric: DistanceMetric,
        name: str,
        config: dict,
    ):
        self.skip_populate = config["skip_populate"]
        self.overwrite = config["overwrite"]
        # We will use the name of the workload as the namespace for the index
        self.name = f"vsb-{name}"
        try:
            self.index = Index(
                url=config["upstash_vector_rest_url"],
                token=config["upstash_vector_rest_token"],
            )
        except Exception as e:
            logger.info(
                "UpstashDB: Failed to connect to index with provided credentials "
                "or index does not exist. Check Upstash Console for details. "
                f"Error: {e}"
            )
            raise StopUser()

        info = self.index.info()
        index_dims = info.dimension
        if dimensions != index_dims:
            raise ValueError(
                f"Upstash Vector index has incorrect dimensions - expected:{dimensions}, found:{index_dims}"
            )
        # Upstash uses the term similariy function instead of metric, but the three metrics used are the same
        index_similarity_function = info.similarity_function
        # Upstash returns the similarity function in all caps, so we need to convert it to lowercase
        index_similarity_function = index_similarity_function.lower()
        # Upstash uses the term "dot_product" instead of "dotproduct"
        if index_similarity_function == "dot_product":
            index_similarity_function = "dotproduct"

        if metric.value != index_similarity_function:
            raise ValueError(
                f"Upstash Vector index has incorrect similarity function - expected:{metric.value}, found:{index_similarity_function}"
            )
        
    def get_batch_size(self, sample_record: Record) -> int:
        # Return the largest batch size possible, based on the following
        # constraints:
        # - Max metadata size is 48KB
        # - Max id length is 1000 bytes
        # - Max namespace length is 255 bytes.
        # - Max dense vector count is 1000
        # - Max sparse vector count is N/A (not supported)
        # Given the above, calculate the maximum possible sized record, based
        # on which fields are present in the sample record.
        max_id = 1000
        max_namespace = 255  # Only one namespace per VectorUpsert request.
        max_values = len(sample_record.values) * 4
        max_metadata = 48 * 1000 if sample_record.metadata else 0
        max_sparse_values = 0  # TODO: Add sparse values when they are supported
        # determine how many we could fit in the max message size of 10MB.
        max_record_size = max_id + max_metadata + max_values + max_sparse_values
        size_based_batch_size = ((10 * 1024 * 1024) - max_namespace) // max_record_size
        max_batch_size = 1000
        batch_size = min(size_based_batch_size, max_batch_size)
        logger.debug(f"UpstashDB.get_batch_size() - Using batch size of {batch_size}")
        return batch_size
    
    def get_namespace(self, namespace: str) -> Namespace:
        # The namespace is the name of the workload
        # The system currently does not initialize the namespace so we add it here
        return UpstashNamespace(self.index, self.name)

    def initialize_population(self):
        # If the index already existed before VSB (we didn't create it) and
        # user didn't specify skip_populate; require --overwrite before
        # deleting the existing index.
        if self.skip_populate:
            return
        if not self.overwrite:
            msg = (
                "UpstashDB: Index already exists - cowardly refusing"
                " to overwrite existing data. Specify --overwrite to delete"
                " it, or specify --skip-populate to skip population phase."
            )
            logger.critical(msg)
            raise StopUser()
        try:
            logger.info(
                "UpstashDB: Clearing existing index before "
                "population (--overwrite=True) "
            )
            logger.info(f"UpstashDB: Index namespace: {self.name}")
            self.index.reset(namespace=self.name)
        except Exception as e:
            # Serverless indexes can throw a "Namespace not found" exception for
            # delete_all if there are no documents in the index. Simply ignore,
            # as the post-condition is the same.
            logger.info(f"UpstashDB: Error deleting index: {e}")
            pass

    def finalize_population(self, record_count: int):
        """Wait until all records are visible in the index"""
        logger.debug(f"UpstashDB: Waiting for record count to reach {record_count}")
        with vsb.logging.progress_task(
            "  Finalize population", "  ✔ Finalize population", total=record_count
        ) as finalize_id:
            while True:
                index_count = self.index.info().vector_count
                if vsb.progress:
                    vsb.progress.update(finalize_id, completed=index_count)
                if index_count >= record_count:
                    logger.debug(
                        f"UpstashDB: Index vector count reached {index_count}, "
                        f"finalize is complete"
                    )
                    break
                time.sleep(1)

    def skip_refinalize(self):
        return False
    
    def get_record_count(self) -> int:
        return self.index.info().vector_count