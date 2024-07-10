# VSB: Vector Search Bench

<p align="center" width="100%">
   <img src=docs/images/splash.jpg width="180px"/>
</p>

**VSB** is a benchmarking suite for vector search. It lets you quickly measure how 
different workloads perform on a range of vector databases.

## Quickstart

### Requirements

VSB has the following requirements:

* Python >= 3.11
* [Docker Compose](https://docs.docker.com/compose/) >= 2.27 (for non-cloud hosted databases)

> [!NOTE]
> macOS ships with an older version of Python (3.9 or earlier). Ensure you have a new enough version of  Python or VSB installation will fail. For example, you can use [Homebrew](https://brew.sh) with the following command:
> 
>`brew install python@3.11`


### Install

Install VSB by following these steps:

1. Clone this repo:

   ```shell
   git clone https://github.com/pinecone-io/VSB.git
   ```

1. Use Poetry to install dependencies:

   ```shell
   cd VSB
   pip3 install poetry && poetry install
   ``` 

1. Activate an environment containing dependencies:

   ```shell
   poetry shell
   ```

### Run

#### Cloud-hosted

To run VSB against a cloud-hosted vector database,
provide suitable credentials for an existing database instance. 

For example, to run the _mnist-test_ workload against a Pinecone index, provide parameters like the following, where `--api_key` specifies the [Pinecone](https://app.pinecone.io) API key to use.

```shell
vsb --database=pinecone --workload=mnist-test \
    --pinecone_api_key=<API_KEY> 
```

#### Local database via Docker

Alternatively, VSB can run against a locally hosted vector database such as
pgvector running in Docker.

To run VSB against a local vector database, follow these steps:


1. Launch the database via `docker compose` in one terminal:

```shell
cd docker/pgvector
docker compose up
```

2. From a second terminal, run VSB:

```shell
vsb --database=pgvector --workload=mnist-test
```

Example output:

<p align="center" width="100%">
   <img src=docs/images/vsb_example_output.png/>
</p>

## Overview

VSB is a CLI tool that runs various workloads against a range of 
vector databases and measure how they perform.

Each experiment consists of three phases: _Setup_, _Populate_, and _Run_:

* **Setup**: Prepares the database and workload for the experiment by creating tables and 
  indexes and downloading or generating data.
* **Populate**: Loads the database with data, creates indexes, etc.
* **Run**: Executes the workload against the database, measuring throughput, latency, 
  and other metrics.

VSB automatically runs these phases in sequence, and reports the results at the 
end. VSB writes detailed results to the `stats.json` file and displays a summary.

### Supported databases

The following databases are currently supported by VSB:

* [Pinecone](vsb/databases/pinecone/README.md)
* [pgvector](vsb/databases/pgvector/README.md)

> [!TIP]
> You can also display the list of supported databases using the following command: 
> `vsb --database=help`

### Supported workloads

VSB currently supports the following workloads:

| Name        | Cardinality | Dimensions |    Metric | Description                                                                                                                                 |
|-------------|------------:|-----------:|----------:|---------------------------------------------------------------------------------------------------------------------------------------------|
| `mnist`     |      60,000 |        784 | euclidean | Images of handwritten digits from [MNIST](https://en.wikipedia.org/wiki/MNIST_database)                                                     |
| `nq768`     |   2,680,893 |        768 |    cosine | Natural language questions from [Google Research](https://ai.google.com/research/NaturalQuestions).                                         |
| `yfcc-10M`  |  10,000,000 |        192 | euclidean | Images from [Yahoo Flickr Creative Commons 100M](https://paperswithcode.com/dataset/yfcc100m) annotated with a "bag" of tags                |
| `cohere768` |  10,000,000 |        768 | euclidean | English Wikipedia articles embedded with Cohere from [wikipedia-22-12](https://huggingface.co/datasets/Cohere/wikipedia-22-12/tree/main/en) |


> You can also display the list of supported workloads using the following command: 
> `vsb --workload=help`

There are also smaller test workloads available for most workloads, such as
`mnist-test` and `nq768-test`. These are designed for basic sanity checking of a test
environment. However, they may not have correct ground-truth nearest neighbors so
should not be used for evaluating recall.

## Usage

The `vsb` command requires two parameters:

* `--database=<database>`: the database to run against.
* `--workload=<workload>`: the workload to execute.

Omitting the value for either `database` or `workload` displays a list of 
available choices. 

Specify additional parameters to further configure the database 
or workload. Some databases require additional parameters, such as  
credentials or a target index. 

Common parameters include the following:

* `--requests_per_sec=<float>`: Cap the rate at which requests are issued to the 
  database.
* `--users=<int>`: Specify the number of concurrent users (connections) to simulate.
* `--skip_populate`: Skip populating the database with data and immediately perform the Run 
  phase.

## Use cases

VSB is designed to help you quickly measure how different workloads perform on a 
range of vector databases. It can be used to perform a range of tasks, including the following:

* Compare the performance of differente vector databases, including throughput, latency, and accuracy;
* Benchmark the performance of a single database across different workloads;
* Evaluate the performance of a database under different conditions, such as different 
  data sizes, dimensions, metrics, and access patterns;
* Understand the performance characteristics and identify the bottlenecks of a database;
* Perform regression testing to ensure that changes to a database do not degrade performance.

### Measuring latency

VSB measures latency by sending a query to the database and measuring the duration 
between issuing the request and receiving the database's response.
This includes both the send/receive time and the time for the database to 
process the request. As such, latency is affected by the RTT between the VSB 
client and the database in addition to how long the database takes to issue a response.

VSB records latency values for each request, then reports these as percentiles 
when the workload completes. It also displays Live values from the last 10 seconds during the 
run for selected percentiles:
<p align="center" width="100%">
<img src=docs/images/vsb_example_live_metrics.png/>
</p>

**Example** 

The following command runs the `yfcc-10M` workload against Pinecone at 10 QPS:

```shell
vsb --database=pinecone --workload=yfcc-10M \
    --pinecone_index_name=<INDEX_NAME> --pinecone_api_key=<API_KEY> \
    --users=10 --requests_per_sec=10
```

#### Designing a latency experiment

When measuring latency, consider the following factors:

* **Requests per second** This is the rate at which requests are issued, specified by the  `--requests_per_sec` parameter. Choose a request rate that is representative of the expected production workload. Avoid values that saturate the client machine or the database server, resulting in elevated latencies.

* **The number of concurrent requests**  to simulate. This is specified by the `--users` parameter. Most production workloads have multiple clients issuing requests to the database concurrently, so it's important to represent this in the experiment.

* **Which metrics to report**. Latency and throughput are classic measures of
  many database systems, but vector database experiments must also consider the
  quality of the responses to queries, such as what
  [recall](https://www.pinecone.io/learn/offline-evaluation/) is achieved at a
  given latency.
 
  Also consider the distribution of recall values. A median (p50) recall of 80% may seem good, but if p10 recall is 0%, then 10% of your queries are returning no relevent results.

### Measuring throughput

VSB measures throughput by calculating the number of responses received over a given period of time. It maintains a running count of the requests issued over the course of the Run phase, and reports the overall rate when the experiment finishes. It also displays a live value over last 10 seconds during the run.

**Example** 

The following command runs the `nq-768` workload against pgvector with multiple users and processes. The goal is to saturate it the database server.

```shell
vsb --database=pgvector --workload=nq768 --users=10 --processes=10
```
#### Designing a throughput experiment

Throughput experiments are typically trying to answer one of two questions:

1. Can the system handle the expected production workload?
1. How far can the system scale within acceptable latency bounds?

In the first case, throughput is an _input_ to the experiment: you can specify the expected 
workload via `--requests_per_sec=N`. In the second case, throughput is an _output_:
you want to generate increasing amounts of load until the response time exceeds
your acceptable bounds, thus identifying the maximum real-world throughput.

By default, VSB only simulates one user (`--users=1`), so the throughput is
effectively the reciprocal of the latency. Bear this in mind when trying to
measure throughput of a system: you typically need to increase the number of `--users` (and potentially `--processes`) to ensure there's sufficient concurrent work given to the database system under test.

## Extending VSB

VSB is extensible, so you can add new databases workloads.

### Adding a new database

To add a new database to VSB, create a new module for your database
and implement 5 required methods, then register with VSB:

1. **Create a new module** in [`vsb/databases/`](vsb/databases/) for your database. For example,
   for `mydb` create `vsb/databases/mydb/mydb.py`.
2. **Implement a Database class in this module**. This class inherits from
   [`database.DB`](vsb/databases/base.py) and implements the required methods:
    * `__init__()` - Set up the connection to your database and any other required 
      initialization.
    * `get_namespace()` - Returns a `Namespace` object to use for 
      the given namespace name. This may be called a "table" or "sub-index." If the database doesn't support multiple namespaces, or if you are developing an initial implemenation, this can return just a single `Namespace` object.
    * `get_batch_size()` - Returns the preferred size of record batch for the populate phase. 
     
3. **Implement optional methods** if applicable to your database, implement the following methods: 
   * `initialize_populate()` - Prepares the database for the populate phase, including tasks like 
     creating a table or clearing existing data.
   * `finalize_populate()` - Finalizes the populate phase, including tasks like creating an index 
     or waiting for upserted data to be processed.
4. **Implement a Namespace class** in this module that inherits from
   [`database.Namespace`](vsb/databases/base.py) and implements the following required
   methods:
    * `upsert_batch()` - Upserts the given batch of records into the namespace. 
    * `search()` - Performs a search for the given query vector.
5. **Register the database with VSB** by adding an entry to the `Database` enum in 
   [`vsb/databases/__init__.py`](vsb/databases/__init__.py) and updating `get_class()`.
6. (Optional) **Add database-specific command-line arguments** to the `add_vsb_cmdline_args()` 
   method in [`vsb/cmdline_args.py`](vsb/cmdline_args.py), such as arguments for passing 
   credentials, connection parameters, or index tunables.
7. (Optional) **Add Docker compose file** to the [`docker`/](docker/) directory to 
   launch a local instance of the database to run tests against. This is only applicable to 
   locally running databases.

You can now run VSB against your database by specifying 
`--database=mydb`.

#### Tips and tricks

* When implementing a new database module, use the existing database modules in VSB as a reference. For example, refer to 
  [`databases/pgvector`](vsb/databases/pgvector) for an example of a locally-running DB, or
  [`database/pinecone`](vsb/databases/pinecone) for a cloud-hosted DB.
* Integration tests exist for each supported database. Run these via `pytest` 
  to check that the module is working correctly. Create a similar test suite for your database.
* The `*-test` workloads are quick to run and a good starting 
  point for testing your database module. For example,
  [workloads/mnist-test](vsb/workloads/mnist/mnist.py) is only 600 records and 20 
  queries and should complete in a few seconds on most databases. 
  Once you have the test workloads working, you can move on to the larger workloads.
* VSB uses standard Python logging, so you can use `logging` to output debug 
  information from your database module. The default emitted log level is `INFO`, 
  but this can be changed via `--loglevel=DEBUG`.

### Adding a new workload

To add a new workload to VSB, create a new module for your workload,
then register it with VSB.

This can be any kind of workload. For example, it could be a synthetic workload, a real-world
dataset, or a workload based on a specific use-case. If the dataset already exists
in Parquet format, you can use the
[`ParquetWorkload`](vsb/workloads/parquet_workload/parquet_workload.py) base class
to simplify this.
Otherwise, implement the full [`VectorWorkload`](vsb/workloads/base.py)
base class.

#### Parquet-based workloads

VSB has support for loading static datasets from Parquet files, assuming the 
files match the
[pinecone-datasets](https://github.com/pinecone-io/pinecone-datasets) schema.

1. **Create a new module** in [`vsb/workloads/`](vsb/workloads/) for your 
   workload. For example, for `my-workload`, create `vsb/workloads/my-workload/my_workload.py`.
2. **Implement a Workload class** in this module that inherits from
   [`parquet_workload.ParquetWorkload`](vsb/workloads/parquet_workload/parquet_workload.py)
   and implements the required methods and properties:
    * `__init__()` - Calls to the superclass constructor passing the dataset path. For example:

      ```python
      class MyWorkload(ParquetWorkload):
          def __init__(self, name: str, cache_dir: str):
              super().__init__(name, "gs://bucket/my_workload", cache_dir=cache_dir)
       ```
    * `dimensions` - The dimensionality of the vectors in the dataset.
    * `metric` - The distance metric to use for the workload.
    * `record_count` - The number of records in the dataset.
    * `request_count` - The number of queries to perform.
3. **Register the workload with VSB** by adding an entry to the `Workload` enum in 
   [`vsb/workloads/__init__.py`](vsb/workloads/__init__.py) and updating `get_class()`.

You can now run this workload by specifying `--workload=my-workload`.

#### Other workloads

If the dataset is not in Parquet format, or if you want to have more control over the
operation of it, then implement the [`VectorWorkload`](vsb/workloads/base.py) base class by following these steps:

1. **Create a new module** in [`vsb/workloads/`](vsb/workloads/) for your
   workload. For example, for `my-workload`, create `vsb/workloads/my-workload/my_workload.py`.
2. **Implement a Workload class** in this module that inherits from
   [`base.VectorWorkload`](vsb/workloads/base.py) and
   implements the required methods and properties:
    * `__init__()` - Whatever initialisation is needed for the workload.
    * `dimensions` - The dimensionality of the vectors in the dataset.
    * `metric` - The distance metric to use for the workload.
    * `record_count` - The number of records in the dataset.
    * `request_count` - The number of queries to perform.
    * `get_sample_record()` - Returns a sample record from the dataset. This is used by
      specific databases to calculate a suitable batch size for the populate phase.
    * `get_record_batch_iter()` - Returns an iterator over a batch of records to
      initially populate the database.
    * `get_query_iter()` - Returns an iterator over the queries a client should
      perform during the Run phase.
3. **Register the workload with VSB** by adding an entry to the `Workload` enum in
   [`vsb/workloads/__init__.py`](vsb/workloads/__init__.py) and updating `get_class()`.

You can now run this workload by specifying `--workload=my-workload`.
