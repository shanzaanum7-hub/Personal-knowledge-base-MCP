"""Search API route.

POST /search — perform semantic search over the authenticated user's knowledge base.

User isolation is enforced by extracting user_id exclusively from the JWT
(via CurrentUserId). The query body never contains or influences the user_id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.security import CurrentUserId
from backend.app.models.search import SearchRequest, SearchResponse
from backend.app.services.search_service import SearchService
from backend.retrieval.retrieval_service import (
    RetrievalDependencyError,
    RetrievalValidationError,
)

router = APIRouter(tags=["Search"])


def _get_search_service() -> SearchService:
    """FastAPI dependency — returns a default SearchService.

    Tests override this with a pre-configured instance via app.dependency_overrides.
    """
    return SearchService()


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic search over the user's knowledge base",
    responses={
        200: {"description": "Ranked results (may be empty with a no-match message)."},
        400: {"description": "Invalid query or top_k value."},
        401: {"description": "Missing or invalid authentication token."},
        422: {"description": "Request body validation error."},
        503: {"description": "Embedding or vector-store service unavailable."},
    },
)
def search_knowledge_base(
    request: SearchRequest,
    user_id: CurrentUserId,
    service: SearchService = Depends(_get_search_service),
) -> SearchResponse:
    """Search the authenticated user's personal knowledge base.

    Embeds the query, performs a cosine-similarity search filtered to the
    authenticated user's documents, and returns ranked text chunks with
    source citations.

    This endpoint performs **retrieval only** — it does not generate an
    LLM answer. Results with a similarity score below the configured
    threshold are excluded; when no confident match exists a message is
    included in the response.

    The ``user_id`` comes exclusively from the bearer token; the request
    body cannot specify or override it.
    """
    try:
        return service.search(
            query=request.query,
            user_id=user_id,
            top_k=request.top_k,
        )
    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RetrievalDependencyError as exc:
        # Embedding provider or Qdrant unreachable — don't expose internals
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The search service is temporarily unavailable. "
                   "Please try again later.",
        ) from exc
