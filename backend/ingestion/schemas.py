"""Data schemas for the ingestion module.

These use lightweight dataclasses so other parts of the application can
depend on predictable, typed structures without pulling heavy runtime
dependencies into the ingestion package.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class Chunk:
    """A single text chunk produced by the ingestion pipeline.

    Fields:
    - doc_id: stable identifier provided by the caller
    - filename: source filename
    - page: 1-based page number for PDFs, or None for text/markdown
    - chunk_id: sequential chunk index within the document (0-based)
    - text: the chunk text
    - metadata: optional freeform dict for additional payload fields
    """

    doc_id: str
    filename: str
    page: Optional[int]
    chunk_id: int
    text: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
