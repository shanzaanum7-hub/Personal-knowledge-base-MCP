# Qdrant Vector Store Contract

`QdrantService` owns the Qdrant client and exposes the interface needed by the
future retrieval service:

```python
service.search(query_vector, user_id, top_k=10) -> list[SearchResult]
```

Each `SearchResult` contains `score`, `text`, `doc_id`, `filename`, `page`, and
`chunk_id`; retrieval code does not need to know Qdrant types or filters.

The service uses one `knowledge_base` collection by default. Every point has a
stable UUID5 derived from `user_id`, `doc_id`, and `chunk_id`, so re-ingesting
the same user's document chunk upserts the existing point instead of creating
duplicates.

The collection uses cosine distance. Its vector dimension is supplied through
`vector_size` or inferred from the first upsert batch, then enforced for all
later operations. It is not hard-coded because the dimension belongs to the
configured embedding model. The Qdrant collection must be initialized with the
same dimension produced by the embedding service.

Every search builds a Qdrant payload filter for `user_id` before returning
results. Stored payload fields are `user_id`, `doc_id`, `filename`, `page`,
`chunk_id`, and `text`.

Empty or malformed inputs, dimension mismatches, invalid `top_k`, unavailable
Qdrant operations, and malformed results raise explicit exceptions.