# Ingestion package: parsing and chunking utilities.
#
# Public API:
# - `parse_file(path) -> (text, metadata)`
# - `chunk_text(text, chunk_size, overlap) -> list[dict]`
#
# Owner: Aliza

from .parser import parse_file  # noqa: F401
from .chunker import chunk_text  # noqa: F401

__all__ = ["parse_file", "chunk_text"]
from .ingest import ingest_document  # noqa: F401
from .pdf_parser import extract_pdf_pages  # noqa: F401

__all__.extend(["ingest_document", "extract_pdf_pages"])
