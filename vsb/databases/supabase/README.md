# Supabase

This directory adds support for running experiments against [Supabase](https://supabase.com/docs/guides/database/extensions/pgvector) - a managed vector database built on top of PostgreSQL and pgvector.

It supports connecting to Supabase databases with pgvector enabled.

To run VSB against a Supabase database:

1. Create a new Supabase project and enable the pgvector extension in your database.

2. Get your database connection string from the Supabase project settings. The connection string should be in the format:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@[HOST]:[PORT]/postgres
   ```

3. Invoke VSB with `--database=supabase` and provide your connection string:

```shell
vsb --database=supabase --workload=mnist-test \
    --supabase_connection_string="postgresql://postgres:[YOUR-PASSWORD]@[HOST]:[PORT]/postgres" \
    --overwrite \
    --supabase_index_type=hnsw \
    --supabase_create_index=after
```

> [!TIP]
> The connection string can also be passed via environment variable
> (`VSB__SUPABASE_CONNECTION_STRING`).

## Supported Features

- Similarity metrics:
  - Cosine similarity
  - Euclidean distance (L2)
  - Max inner product (generalization of dot product)
- Index types:
  - HNSW
  - IVFFlat
- Automatic index creation and optimization
- Batch operations for insert, update, search, and delete
- Metadata filtering

## Notes

- Collections can be queried immediately after creation, but for optimal performance, indexing is performed after the population phase is complete
- The default batch size is 500 records
- You can create an index either before or after the population phase. If you create it after the population phase, the index will be created after the final batch of records has been ingested and this operation might take a while to complete and may fail if the index is too large. In this case, consider creating the index before the population phase.