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

from backend.app.services.document_service import DocumentService
from backend.app.core.config import get_settings
from qdrant_client import models as qdrant_models


_document_service = DocumentService()


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



@mcp.tool()
def list_sources(user_id: str) -> dict:
    """List documents (sources) belonging to the authenticated user.

    Returns a JSON-serializable dict with `results` (list of documents) and
    optional `message`. Errors return an error payload consistent with other
    MCP tool responses.
    """
    try:
        docs = _document_service.list_documents(user_id=user_id)
        return {
            "results": [
                {"doc_id": d.doc_id, "filename": d.filename} for d in docs
            ],
            "message": None,
        }
    except Exception:
        return {
            "error": "dependency_error",
            "message": (
                "The document service is temporarily unavailable. "
                "Please try again later."
            ),
        }


@mcp.tool()
def get_document(doc_id: str, user_id: str) -> dict:
    """Return all stored chunks for a document belonging to the user.

    The `user_id` must be the authenticated user's ID (in MCP deployments the
    caller must provide a validated identity). The implementation reuses the
    existing `DocumentService`/Qdrant scroll API to avoid duplicating logic.
    """
    try:
        # Build a Qdrant payload filter restricting to this user and document
        user_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="user_id",
                    match=qdrant_models.MatchValue(value=user_id),
                ),
                qdrant_models.FieldCondition(
                    key="doc_id",
                    match=qdrant_models.MatchValue(value=doc_id),
                ),
            ]
        )

        points, _ = _document_service._get_vector_store().scroll(
            collection_name=get_settings().qdrant_collection,
            scroll_filter=user_filter,
            limit=1000,
            with_payload=True,
        )

        chunks = []
        for p in points:
            payload = getattr(p, "payload", {}) or {}
            chunks.append(
                {
                    "text": payload.get("text"),
                    "chunk_id": payload.get("chunk_id"),
                    "page": payload.get("page"),
                    "filename": payload.get("filename"),
                }
            )

        return {"doc_id": doc_id, "chunks": chunks, "message": None}
    except Exception:
        return {
            "error": "dependency_error",
            "message": (
                "The document service is temporarily unavailable. "
                "Please try again later."
            ),
        }


if __name__ == "__main__":
    mcp.run()