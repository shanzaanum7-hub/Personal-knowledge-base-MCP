"""Document service — orchestrates ingestion, embedding, and vector storage.

This is the only place in the application layer that coordinates the three
downstream modules owned by Aliza (ingestion) and Samia (embeddings, vector_store).
Route handlers must call this service and must never import those modules directly.
"""

from __future__ import annotations

import os
import tempfile
from typing import Protocol, runtime_checkable

from fastapi import UploadFile

from backend.app.models.document import ChunkInfo, DocumentMeta, UploadResponse
from backend.ingestion.ingest import IngestionError, ingest_document
from backend.ingestion.schemas import Chunk


# ---------------------------------------------------------------------------
# Protocols — allow dependency injection in tests without live services
# ---------------------------------------------------------------------------

@runtime_checkable
class EmbeddingDependency(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class VectorStoreDependency(Protocol):
    def upsert_vectors(
        self,
        user_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None: ...

    def scroll(
        self,
        collection_name: str,
        scroll_filter: object,
        limit: int,
        with_payload: bool,
    ) -> tuple[list, object | None]: ...

    def delete_document_points(
        self,
        user_id: str,
        doc_id: str,
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Allowed file types
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".txt", ".md", ".markdown"})
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "text/plain",
        "text/markdown",
        # browsers sometimes send these for .md files
        "text/x-markdown",
        "application/octet-stream",
    }
)


def _file_extension(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


def _validate_upload(file: UploadFile) -> str:
    """Return the lowercased file extension or raise ValueError."""
    filename = file.filename or ""
    ext = _file_extension(filename)
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext or '(none)'}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def _doc_id_from_filename(filename: str) -> str:
    """Derive a stable doc_id from the original filename (no extension)."""
    return os.path.splitext(os.path.basename(filename))[0]


def _chunk_preview(text: str, length: int = 120) -> str:
    preview = text.strip()
    return preview[:length] + "…" if len(preview) > length else preview


# ---------------------------------------------------------------------------
# DocumentService
# ---------------------------------------------------------------------------

class DocumentService:
    """Coordinate upload → ingestion → embedding → vector storage.

    Parameters
    ----------
    embedding_service:
        Any object with ``embed_texts(texts) -> list[list[float]]``.
        Defaults to a real ``EmbeddingService`` instance on first use.
    vector_store:
        Any object with ``upsert_vectors`` and ``scroll``.
        Defaults to a real ``QdrantService`` instance on first use.
    settings:
        Application settings. Defaults to ``get_settings()``.
    """

    def __init__(
        self,
        embedding_service: EmbeddingDependency | None = None,
        vector_store: VectorStoreDependency | None = None,
        settings=None,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._settings = settings

    def _get_settings(self):
        if self._settings is None:
            from backend.app.core.config import get_settings
            self._settings = get_settings()
        return self._settings

    def _get_embedding_service(self) -> EmbeddingDependency:
        if self._embedding_service is None:
            from backend.embeddings.embedding_service import EmbeddingService
            self._embedding_service = EmbeddingService(self._get_settings())
        return self._embedding_service

    def _get_vector_store(self) -> VectorStoreDependency:
        if self._vector_store is None:
            from backend.vector_store.qdrant_service import QdrantService
            self._vector_store = QdrantService(settings=self._get_settings())
        return self._vector_store

    # -- public API ---------------------------------------------------------

    async def ingest_upload(
        self,
        file: UploadFile,
        user_id: str,
    ) -> UploadResponse:
        """Process an uploaded file end-to-end and return an upload summary.

        Steps
        -----
        1. Validate file extension.
        2. Write the upload to a temp file (needed by path-based ingestion).
        3. Run ``ingest_document`` (Aliza's pipeline).
        4. Embed all chunk texts (Samia's embedding service).
        5. Upsert vectors with ``user_id`` payload (Samia's vector store).
        6. Return an ``UploadResponse`` with chunk summaries.

        Raises
        ------
        ValueError
            Invalid file type or empty file.
        IngestionError
            Ingestion pipeline rejects the file.
        RuntimeError
            Embedding or vector-store failure.
        """
        _validate_upload(file)

        filename = file.filename or "upload"
        doc_id = _doc_id_from_filename(filename)
        ext = _file_extension(filename)

        # Read upload content once — UploadFile is a stream
        content = await file.read()
        if not content:
            raise ValueError("Uploaded file is empty")

        # Write to a named temp file so ingest_document can open it by path
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # --- Step 3: ingestion (Aliza) ---
            try:
                chunks = ingest_document(tmp_path, doc_id=doc_id)
            except IngestionError as exc:
                raise IngestionError(str(exc)) from exc

            if not chunks:
                raise ValueError(
                    "No content could be extracted from the uploaded file. "
                    "The file may be empty or contain only images."
                )

            # Stamp the original filename onto every chunk (temp path differs)
            for chunk in chunks:
                chunk.filename = filename

            # --- Step 4: embed (Samia) ---
            texts = [chunk.text for chunk in chunks]
            try:
                vectors = self._get_embedding_service().embed_texts(texts)
            except Exception as exc:
                raise RuntimeError(
                    f"Embedding failed for '{filename}': {exc}"
                ) from exc

            # --- Step 5: store (Samia) ---
            try:
                self._get_vector_store().upsert_vectors(user_id, chunks, vectors)
            except Exception as exc:
                raise RuntimeError(
                    f"Vector storage failed for '{filename}': {exc}"
                ) from exc

        finally:
            # Always remove the temp file, even on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return UploadResponse(
            doc_id=doc_id,
            filename=filename,
            chunk_count=len(chunks),
            chunks=[
                ChunkInfo(
                    chunk_id=chunk.chunk_id,
                    page=chunk.page,
                    text_preview=_chunk_preview(chunk.text),
                )
                for chunk in chunks
            ],
        )

    def list_documents(
        self,
        user_id: str,
        limit: int = 256,
    ) -> list[DocumentMeta]:
        """Return distinct documents stored for a user.

        Scrolls the Qdrant collection, filtering by ``user_id``, and
        de-duplicates by ``doc_id`` to return one record per document.

        Parameters
        ----------
        user_id:
            The authenticated user's ID — never accepted from the client.
        limit:
            Maximum number of *points* to scroll before de-duplicating.
            Sufficient for typical personal knowledge bases.
        """
        from qdrant_client import models as qdrant_models

        user_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="user_id",
                    match=qdrant_models.MatchValue(value=user_id),
                )
            ]
        )

        try:
            points, _ = self._get_vector_store().scroll(
                collection_name=self._get_settings().qdrant_collection,
                scroll_filter=user_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Could not list documents: {exc}") from exc

        seen: dict[str, str] = {}  # doc_id → filename
        for point in points:
            payload = point.payload or {}
            doc_id = payload.get("doc_id")
            fn = payload.get("filename")
            if isinstance(doc_id, str) and doc_id and isinstance(fn, str) and fn:
                seen.setdefault(doc_id, fn)

        return [
            DocumentMeta(doc_id=did, filename=fn)
            for did, fn in sorted(seen.items())
        ]

    def delete_document(self, doc_id: str, user_id: str) -> bool:
        """Delete all vectors for doc_id belonging exclusively to user_id.

        Returns True if points were found and deleted, False otherwise.
        """
        try:
            return self._get_vector_store().delete_document_points(
                user_id=user_id,
                doc_id=doc_id,
            )
        except Exception as exc:
            raise RuntimeError(f"Could not delete document '{doc_id}': {exc}") from exc
