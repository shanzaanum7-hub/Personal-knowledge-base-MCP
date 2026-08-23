"""Pydantic request/response models for document endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentMeta(BaseModel):
    """Minimal document record returned in listing responses."""

    doc_id: str = Field(..., description="Stable document identifier.")
    filename: str = Field(..., description="Original filename as uploaded.")


class ChunkInfo(BaseModel):
    """Summary of one ingested chunk, included in the upload response."""

    chunk_id: int = Field(..., description="0-based sequential index within the document.")
    page: int | None = Field(None, description="1-based page number (PDFs only).")
    text_preview: str = Field(
        ..., description="First 120 characters of the chunk text."
    )


class UploadResponse(BaseModel):
    """Response returned after a successful document upload and ingestion."""

    doc_id: str = Field(..., description="Stable identifier assigned to this document.")
    filename: str = Field(..., description="Original filename as uploaded.")
    chunk_count: int = Field(..., description="Number of chunks stored in the vector database.")
    chunks: list[ChunkInfo] = Field(
        ..., description="Brief summary of every stored chunk."
    )
