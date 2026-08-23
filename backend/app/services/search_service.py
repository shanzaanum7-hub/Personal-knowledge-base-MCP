"""Search service — thin application-layer wrapper around RetrievalService.

Route handlers import this service only; they must never import
RetrievalService directly. This keeps the API layer decoupled from the
retrieval implementation owned by Samia.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.app.models.search import SearchResponse, SearchResult
from backend.retrieval.retrieval_service import (
    RetrievalDependencyError,
    RetrievalResponse,
    RetrievalService,
    RetrievalValidationError,
)


# ---------------------------------------------------------------------------
# Protocol — allows test injection without live Qdrant/OpenAI
# ---------------------------------------------------------------------------

@runtime_checkable
class RetrievalDependency(Protocol):
    def search(
        self,
        query: str,
        user_id: str,
        top_k: int,
    ) -> RetrievalResponse: ...


# ---------------------------------------------------------------------------
# SearchService
# ---------------------------------------------------------------------------

class SearchService:
    """Translate API-layer search requests into retrieval service calls.

    Parameters
    ----------
    retrieval_service:
        Any object satisfying ``RetrievalDependency``.
        Defaults to a real ``RetrievalService`` on first use.
    settings:
        Application settings forwarded to the retrieval service.
        Defaults to ``get_settings()``.
    """

    def __init__(
        self,
        retrieval_service: RetrievalDependency | None = None,
        settings=None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._settings = settings

    def _get_retrieval_service(self) -> RetrievalDependency:
        if self._retrieval_service is None:
            from backend.app.core.config import get_settings
            self._retrieval_service = RetrievalService(
                settings=self._settings or get_settings()
            )
        return self._retrieval_service

    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
    ) -> SearchResponse:
        """Execute a user-scoped semantic search.

        Parameters
        ----------
        query:
            Natural-language search query.  Must be non-empty (validated
            earlier by the Pydantic model, but ``RetrievalService`` also
            validates independently).
        user_id:
            Authenticated user ID — injected from the JWT, never from the
            request body.
        top_k:
            Maximum number of ranked results to return (1–50).

        Returns
        -------
        SearchResponse
            Contains the original query, ranked results, and an optional
            no-match message when no confident results exist.

        Raises
        ------
        RetrievalValidationError
            If the query is blank or top_k is out of range.
        RetrievalDependencyError
            If the embedding provider or Qdrant call fails.
        """
        retrieval_response: RetrievalResponse = self._get_retrieval_service().search(
            query=query,
            user_id=user_id,
            top_k=top_k,
        )

        results = [
            SearchResult(
                score=r.score,
                text=r.text,
                filename=r.filename,
                page=r.page,
                chunk_id=r.chunk_id,
                doc_id=r.doc_id,
            )
            for r in retrieval_response.results
        ]

        return SearchResponse(
            query=query,
            results=results,
            message=retrieval_response.message,
        )
