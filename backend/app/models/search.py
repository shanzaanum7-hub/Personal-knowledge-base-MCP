"""Pydantic request/response models for the search endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# Hard cap that matches RetrievalService.DEFAULT_MAX_TOP_K = 50.
_MAX_TOP_K = 50


class SearchRequest(BaseModel):
    """Body of POST /search."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural-language query to search the knowledge base.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=_MAX_TOP_K,
        description=f"Maximum number of results to return (1–{_MAX_TOP_K}).",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank or whitespace only")
        return v


class SearchResult(BaseModel):
    """A single ranked result chunk."""

    score: float = Field(..., description="Cosine similarity score (0–1).")
    text: str = Field(..., description="The matched text chunk.")
    filename: str = Field(..., description="Source document filename.")
    page: int | None = Field(None, description="Source page (PDFs only).")
    chunk_id: int = Field(..., description="Chunk index within the document.")
    doc_id: str = Field(..., description="Stable document identifier.")


class SearchResponse(BaseModel):
    """Response returned by POST /search."""

    query: str = Field(..., description="The original query string.")
    results: list[SearchResult] = Field(
        ..., description="Ranked list of matching chunks."
    )
    message: str | None = Field(
        None,
        description=(
            "Set when no confident match was found. "
            "Null when results are present."
        ),
    )
