"""Simple document parsers for .txt and .md files, with optional PDF support.

This module provides a minimal, dependency-light implementation suitable for
Phase 1. PDF parsing uses `pypdf` if available; if not, a clear ImportError
is raised when attempting to parse PDFs.
"""
from typing import Tuple, Dict


def parse_text_file(path: str) -> Tuple[str, Dict]:
    """Read a text or markdown file and return (text, metadata)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    metadata = {"filename": path}
    return text, metadata


def parse_pdf_file(path: str) -> Tuple[str, Dict]:
    """Parse a PDF file using pypdf (if installed). Returns concatenated text."""
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise ImportError(
            "PDF parsing requires the 'pypdf' package. Install it or avoid PDF files for Phase 1."
        ) from e

    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n\n".join(pages)
    metadata = {"filename": path, "num_pages": len(reader.pages)}
    return text, metadata


def parse_file(path: str) -> Tuple[str, Dict]:
    """Auto-detect file type by extension and parse accordingly.

    Supported: .txt, .md (or .markdown), .pdf (requires pypdf).
    """
    lower = path.lower()
    if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".markdown"):
        return parse_text_file(path)
    if lower.endswith(".pdf"):
        return parse_pdf_file(path)
    raise ValueError(f"Unsupported file type for parsing: {path}")
