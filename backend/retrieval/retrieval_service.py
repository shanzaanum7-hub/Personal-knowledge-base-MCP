"""Application-level semantic retrieval over embeddings and Qdrant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.app.core.config import Settings, get_settings
from backend.embeddings.embedding_service import EmbeddingService
from backend.vector_store.qdrant_service import QdrantService, SearchResult


NO_CONFIDENT_MATCH_MESSAGE = "No confident match found in your knowledge base."
NO_RESULTS_MESSAGE = "No results found in your knowledge base."
DEFAULT_SIMILARITY_THRESHOLD = 0.70
DEFAULT_MAX_TOP_K = 50


class RetrievalError(RuntimeError):
    """Base exception for retrieval validation and dependency failures."""


class RetrievalValidationError(RetrievalError, ValueError):
    """Raised when a retrieval request is invalid."""


class RetrievalDependencyError(RetrievalError):
    """Raised when embedding or vector-store operations fail."""


@dataclass(frozen=True)
class SourceCitation:
    """Source metadata suitable for frontend and MCP responses."""

    doc_id: str
    filename: str
    page: int | None
    chunk_id: int


@dataclass(frozen=True)
class RetrievedResult:
    """A ranked result with both flat fields and a citation object."""

    score: float
    text: str
    doc_id: str
    filename: str
    page: int | None
    chunk_id: int

    @property
    def source(self) -> SourceCitation:
        return SourceCitation(
            doc_id=self.doc_id,
            filename=self.filename,
            page=self.page,
            chunk_id=self.chunk_id,
        )


@dataclass(frozen=True)
class RetrievalResponse:
    """Retrieval results and an optional user-facing no-match message."""

    results: list[RetrievedResult]
    message: str | None = None


class EmbeddingDependency(Protocol):
    def embed_text(self, text: str) -> list[float]:
        ...


class VectorStoreDependency(Protocol):
    def search(
        self, query_vector: list[float], user_id: str, top_k: int
    ) -> list[SearchResult]:
        ...


class RetrievalService:
    """Coordinate query embedding, user-scoped search, and thresholding."""

    def __init__(
        self,
        embedding_service: EmbeddingDependency | None = None,
        vector_store: VectorStoreDependency | None = None,
        settings: Settings | None = None,
        similarity_threshold: float | None = None,
        max_top_k: int = DEFAULT_MAX_TOP_K,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)
        self.vector_store = vector_store or QdrantService(settings=self.settings)
        self.max_top_k = self._validate_max_top_k(max_top_k)
        configured_threshold = getattr(
            self.settings, "retrieval_similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
        )
        self.similarity_threshold = self._validate_threshold(
            configured_threshold if similarity_threshold is None else similarity_threshold
        )

    def search(self, query: str, user_id: str, top_k: int = 10) -> RetrievalResponse:
        """Return confident, ranked results for a user-scoped natural-language query."""
        self._validate_query(query)
        self._validate_user_id(user_id)
        self._validate_top_k(top_k)

        try:
            query_vector = self.embedding_service.embed_text(query)
        except Exception as exc:
            raise RetrievalDependencyError(
                f"Could not generate query embedding: {exc}"
            ) from exc

        try:
            candidates = self.vector_store.search(query_vector, user_id, top_k)
        except Exception as exc:
            raise RetrievalDependencyError(
                f"Could not search the vector store: {exc}"
            ) from exc

        ranked = sorted(candidates, key=lambda result: result.score, reverse=True)
        confident = [
            self._to_result(result)
            for result in ranked
            if result.score >= self.similarity_threshold
        ]
        if confident:
            return RetrievalResponse(results=confident)
        message = NO_RESULTS_MESSAGE if not ranked else NO_CONFIDENT_MATCH_MESSAGE
        return RetrievalResponse(results=[], message=message)

    def search_notes(self, query: str, user_id: str, top_k: int = 10) -> RetrievalResponse:
        """MCP-friendly alias that keeps embedding and Qdrant details private."""
        return self.search(query=query, user_id=user_id, top_k=top_k)

    def _validate_top_k(self, top_k: int) -> None:
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
            or top_k > self.max_top_k
        ):
            raise RetrievalValidationError(
                f"top_k must be an integer between 1 and {self.max_top_k}"
            )

    @staticmethod
    def _validate_max_top_k(max_top_k: int) -> int:
        if not isinstance(max_top_k, int) or isinstance(max_top_k, bool) or max_top_k < 1:
            raise RetrievalValidationError("max_top_k must be a positive integer")
        return max_top_k

    @staticmethod
    def _validate_query(query: str) -> None:
        if not isinstance(query, str) or not query.strip():
            raise RetrievalValidationError("query must be a non-empty string")

    @staticmethod
    def _validate_user_id(user_id: str) -> None:
        if not isinstance(user_id, str) or not user_id.strip():
            raise RetrievalValidationError("user_id must be a non-empty string")

    @staticmethod
    def _validate_threshold(threshold: Any) -> float:
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not 0.0 <= float(threshold) <= 1.0
        ):
            raise RetrievalValidationError("similarity_threshold must be between 0 and 1")
        return float(threshold)

    @staticmethod
    def _to_result(result: SearchResult) -> RetrievedResult:
        return RetrievedResult(
            score=result.score,
            text=result.text,
            doc_id=result.doc_id,
            filename=result.filename,
            page=result.page,
            chunk_id=result.chunk_id,
        )