"""FastMCP server for the Personal Knowledge-Base."""

from __future__ import annotations

from fastmcp import FastMCP

from backend.retrieval.retrieval_service import (
    RetrievalDependencyError,
    RetrievalService,
    RetrievalValidationError,
)

mcp = FastMCP("Personal Knowledge-Base")

_retrieval_service = RetrievalService()


@mcp.tool()
def search_notes(
    query: str,
    user_id: str,
    top_k: int = 10,
) -> dict:
    """Search the authenticated user's personal knowledge base.

    Args:
        query: Natural-language question or search query.
        user_id: ID of the authenticated user.
        top_k: Maximum number of results to return.

    Returns:
        Ranked matching chunks with source citations, or a no-match message.
    """
    try:
        response = _retrieval_service.search_notes(
            query=query,
            user_id=user_id,
            top_k=top_k,
        )

        return {
            "results": [
                {
                    "score": result.score,
                    "text": result.text,
                    "doc_id": result.doc_id,
                    "filename": result.filename,
                    "page": result.page,
                    "chunk_id": result.chunk_id,
                }
                for result in response.results
            ],
            "message": response.message,
        }

    except RetrievalValidationError as exc:
        return {
            "error": "validation_error",
            "message": str(exc),
        }

    except RetrievalDependencyError:
        return {
            "error": "dependency_error",
            "message": (
                "The search service is temporarily unavailable. "
                "Please try again later."
            ),
        }


if __name__ == "__main__":
    mcp.run()