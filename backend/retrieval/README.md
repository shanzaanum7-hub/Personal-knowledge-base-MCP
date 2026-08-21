# Retrieval Service Contract

`RetrievalService.search(query, user_id, top_k=10)` coordinates query
embedding and user-scoped Qdrant search. `search_notes` is an equivalent
MCP-facing alias; neither caller needs to know provider or Qdrant details.

The service validates non-empty queries, requires a user ID, and limits `top_k`
to 1 through 50. It embeds the query once, passes the resulting vector and
`user_id` to the vector store, sorts candidates by descending score, and keeps
only results with `score >= 0.70` by default.

The threshold is injectable through `similarity_threshold` and will also honor
a future `retrieval_similarity_threshold` field on the shared settings object.
The current shared settings module does not yet define that field, so the
constructor is the supported configuration point without modifying another
developer's module.

Successful results are `RetrievedResult` objects containing `score`, `text`,
`doc_id`, `filename`, `page`, `chunk_id`, and a frontend/MCP-friendly
`source` citation containing the document metadata. Empty results return a
clear message: either `No results found in your knowledge base.` or
`No confident match found in your knowledge base.`

Embedding and vector-store failures are wrapped as `RetrievalDependencyError`;
invalid requests raise `RetrievalValidationError`.