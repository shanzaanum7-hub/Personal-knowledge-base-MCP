"""Qdrant-backed vector storage for embedded document chunks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID, uuid5

from qdrant_client import QdrantClient, models

from backend.app.core.config import Settings, get_settings
from backend.ingestion.schemas import Chunk


Vector = list[float]
_POINT_NAMESPACE = UUID("f7c6a1f8-42aa-4d4f-8d03-7c6f5c50a8e6")


class VectorStoreError(RuntimeError):
    """Base exception for vector-store failures."""


class VectorStoreValidationError(VectorStoreError, ValueError):
    """Raised when vectors, chunks, or search arguments are invalid."""


class VectorStoreConnectionError(VectorStoreError):
    """Raised when Qdrant cannot be reached or returns an operation error."""


@dataclass(frozen=True)
class SearchResult:
    """Qdrant-independent result consumed by the retrieval service."""

    score: float
    text: str
    doc_id: str
    filename: str
    page: int | None
    chunk_id: int


class QdrantClientProtocol(Protocol):
    """Client surface used by this service, enabling mock-based tests."""

    def collection_exists(self, collection_name: str) -> bool:
        ...


class QdrantService:
    """Store and search vectors in one payload-filtered Qdrant collection.

    ``vector_size`` is optional on construction. When omitted, the first
    upsert infers it from its vectors and subsequent operations enforce it.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: QdrantClientProtocol | None = None,
        collection_name: str | None = None,
        vector_size: int | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection_name = (
            collection_name if collection_name is not None else self.settings.qdrant_collection
        )
        if not isinstance(self.collection_name, str) or not self.collection_name.strip():
            raise VectorStoreValidationError("collection_name must not be empty")
        self._vector_size = self._validate_dimension(vector_size)
        self._client = client

    def initialize(self, vector_size: int | None = None) -> None:
        """Create the collection if needed, using cosine distance."""
        dimension = self._resolve_dimension(vector_size)
        try:
            exists = self._get_client().collection_exists(self.collection_name)
            if not exists:
                self._get_client().create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=dimension,
                        distance=models.Distance.COSINE,
                    ),
                )
            self._vector_size = dimension
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Could not initialize Qdrant collection '{self.collection_name}': {exc}"
            ) from exc

    def upsert_vectors(
        self,
        user_id: str,
        chunks: Sequence[Chunk | Mapping[str, Any]],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        """Upsert chunk vectors while preserving metadata and stable IDs."""
        self._validate_user_id(user_id)
        if isinstance(chunks, (str, bytes)) or not isinstance(chunks, Sequence):
            raise VectorStoreValidationError("chunks must be a sequence")
        if isinstance(vectors, (str, bytes)) or not isinstance(vectors, Sequence):
            raise VectorStoreValidationError("vectors must be a sequence")
        if not chunks:
            raise VectorStoreValidationError("chunks must not be empty")
        if len(chunks) != len(vectors):
            raise VectorStoreValidationError("chunks and vectors must have equal lengths")

        normalized_vectors = [self._validate_vector(vector) for vector in vectors]
        dimension = len(normalized_vectors[0])
        if any(len(vector) != dimension for vector in normalized_vectors):
            raise VectorStoreValidationError("vectors must have consistent dimensions")
        self._ensure_dimension(dimension)
        points = []
        for chunk, vector in zip(chunks, normalized_vectors):
            payload = self._payload(user_id, chunk)
            point_id = self._stable_point_id(user_id, payload["doc_id"], payload["chunk_id"])
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))

        self.initialize(dimension)
        try:
            self._get_client().upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Could not upsert vectors into '{self.collection_name}': {exc}"
            ) from exc

    def search(
        self,
        query_vector: Sequence[float],
        user_id: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Return ranked results restricted to one user's payload."""
        self._validate_user_id(user_id)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise VectorStoreValidationError("top_k must be a positive integer")
        vector = self._validate_vector(query_vector)
        self._ensure_dimension(len(vector))
        user_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                )
            ]
        )
        try:
            points = self._get_client().search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=user_filter,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            # If Qdrant is unreachable (common in local dev), return no
            # candidates instead of failing the whole retrieval service.
            # Keep raising for non-connection errors by checking for
            # common network/connectivity indicators in the exception.
            msg = str(exc).lower()
            connection_indicators = (
                "getaddrinfo failed",
                "connectionrefusederror",
                "connecterror",
                "failed to establish a new connection",
            )
            if any(ind in msg for ind in connection_indicators):
                return []
            raise VectorStoreConnectionError(
                f"Could not search Qdrant collection '{self.collection_name}': {exc}"
            ) from exc
        return [self._to_search_result(point) for point in points]

    def scroll(
        self,
        collection_name: str | None = None,
        scroll_filter: Any = None,
        limit: int = 100,
        with_payload: bool = True,
    ) -> tuple[list, Any]:
        """Scroll points in the collection with optional payload filtering."""
        target_collection = collection_name or self.collection_name
        try:
            return self._get_client().scroll(
                collection_name=target_collection,
                scroll_filter=scroll_filter,
                limit=limit,
                with_payload=with_payload,
            )
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Could not scroll points in '{target_collection}': {exc}"
            ) from exc

    def delete_document_points(
        self,
        user_id: str,
        doc_id: str,
    ) -> bool:
        """Delete all points belonging to a specific user_id and doc_id.

        Returns True if points were found and deleted, False if none matched.
        """
        self._validate_user_id(user_id)
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise VectorStoreValidationError("doc_id must be a non-empty string")

        doc_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                ),
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=doc_id),
                ),
            ]
        )

        try:
            existing_points, _ = self._get_client().scroll(
                collection_name=self.collection_name,
                scroll_filter=doc_filter,
                limit=1,
                with_payload=False,
            )
            if not existing_points:
                return False

            self._get_client().delete(
                collection_name=self.collection_name,
                points_selector=doc_filter,
                wait=True,
            )
            return True
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Could not delete document points for '{doc_id}' in '{self.collection_name}': {exc}"
            ) from exc

    def _get_client(self) -> QdrantClientProtocol:
        if self._client is None:
            try:
                self._client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key or None,
                )
            except Exception as exc:
                raise VectorStoreConnectionError(
                    f"Could not create Qdrant client: {exc}"
                ) from exc
        return self._client

    def _resolve_dimension(self, vector_size: int | None) -> int:
        requested = self._validate_dimension(vector_size)
        if requested is not None and self._vector_size is not None and requested != self._vector_size:
            raise VectorStoreValidationError("vector_size does not match configured dimension")
        dimension = requested or self._vector_size
        if dimension is None:
            raise VectorStoreValidationError(
                "vector_size is required before collection initialization"
            )
        return dimension

    def _ensure_dimension(self, dimension: int) -> None:
        if self._vector_size is None:
            self._vector_size = dimension
        elif self._vector_size != dimension:
            raise VectorStoreValidationError(
                f"vector dimension {dimension} does not match collection dimension {self._vector_size}"
            )

    @staticmethod
    def _validate_dimension(vector_size: int | None) -> int | None:
        if vector_size is not None and (
            not isinstance(vector_size, int) or isinstance(vector_size, bool) or vector_size < 1
        ):
            raise VectorStoreValidationError("vector_size must be a positive integer")
        return vector_size

    @staticmethod
    def _validate_user_id(user_id: str) -> None:
        if not isinstance(user_id, str) or not user_id.strip():
            raise VectorStoreValidationError("user_id must be a non-empty string")

    @staticmethod
    def _validate_vector(vector: Sequence[float]) -> Vector:
        if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
            raise VectorStoreValidationError("vectors must be sequences of numbers")
        if not vector:
            raise VectorStoreValidationError("vectors must not be empty")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector):
            raise VectorStoreValidationError("vectors must contain only numbers")
        return [float(value) for value in vector]

    @staticmethod
    def _payload(user_id: str, chunk: Chunk | Mapping[str, Any]) -> dict[str, Any]:
        def value(name: str) -> Any:
            if isinstance(chunk, Mapping):
                return chunk.get(name)
            return getattr(chunk, name, None)

        payload = {
            "user_id": user_id,
            "doc_id": value("doc_id"),
            "filename": value("filename"),
            "page": value("page"),
            "chunk_id": value("chunk_id"),
            "text": value("text"),
        }
        if not isinstance(payload["doc_id"], str) or not payload["doc_id"]:
            raise VectorStoreValidationError("each chunk requires a non-empty doc_id")
        if not isinstance(payload["filename"], str) or not payload["filename"]:
            raise VectorStoreValidationError("each chunk requires a non-empty filename")
        if not isinstance(payload["text"], str) or not payload["text"].strip():
            raise VectorStoreValidationError("each chunk requires non-empty text")
        if not isinstance(payload["chunk_id"], int) or isinstance(payload["chunk_id"], bool):
            raise VectorStoreValidationError("each chunk requires an integer chunk_id")
        return payload

    @staticmethod
    def _stable_point_id(user_id: str, doc_id: str, chunk_id: int) -> str:
        identity = f"{user_id}\0{doc_id}\0{chunk_id}"
        return str(uuid5(_POINT_NAMESPACE, identity))

    @staticmethod
    def _to_search_result(point: Any) -> SearchResult:
        payload = point.payload
        required = ("text", "doc_id", "filename", "chunk_id")
        if not isinstance(payload, Mapping) or any(key not in payload for key in required):
            raise VectorStoreError("Qdrant result is missing required payload fields")
        return SearchResult(
            score=float(point.score),
            text=payload["text"],
            doc_id=payload["doc_id"],
            filename=payload["filename"],
            page=payload.get("page"),
            chunk_id=payload["chunk_id"],
        )