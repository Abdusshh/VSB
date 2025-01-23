# Upstash

This directory adds support running experiments against [Upstash Vector](https://upstash.com/docs/vector/overall/getstarted) - a managed vector database.

It supports connecting to Serverless indexes.

To run VSB against an Upstash index:

1. Create a new Upstash Vector index with the correct dimensionality and similarity function on the [Upstash Console](https://console.upstash.com/).

2. Obtain the REST URL and token from the Upstash Console.

3. Invoke VSB with `--database=upstash` and provide your REST URL and token to VSB.

```shell
vsb --database=upstash --workload=mnist-test \
    --upstash_vector_rest_url=<YOUR_REST_URL> \
    --upstash_vector_rest_token=<YOUR_REST_TOKEN>
```

> [!TIP]
> The REST URL and token can also be passed via environment variables
> (`VSB__UPSTASH_VECTOR_REST_TOKEN` and `VSB__UPSTASH_VECTOR_REST_URL` respectively).
