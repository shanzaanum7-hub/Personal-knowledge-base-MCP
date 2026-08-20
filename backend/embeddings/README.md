# Embedding Service Contract

`EmbeddingService` consumes text strings, including the `text` field from
ingestion `Chunk` objects. It exposes:

- `embed_text(text: str) -> list[float]`
- `embed_texts(texts: Sequence[str]) -> list[list[float]]`

The default provider is OpenAI with the configured
`text-embedding-3-small` model. Provider and model values come from the shared
application settings (`EMBEDDING_PROVIDER` and `EMBEDDING_MODEL`); the OpenAI
client reads `OPENAI_API_KEY` from the environment. The OpenAI SDK must be
installed by the application environment.

Batch results preserve input order and all vectors in one response must have
the same dimension. Empty or invalid input, unsupported providers, provider
failures, missing dependencies, and malformed responses raise clear
exceptions; fake vectors are never returned.

The vector dimension is determined by the selected embedding model and is not
hard-coded here. The next Qdrant integration should configure its collection
with the dimension of the selected model and store the returned vectors.