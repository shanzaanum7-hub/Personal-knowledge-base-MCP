"""PDF parser that extracts page-level text using pypdf.

Returns a list of (page_number, text) tuples where page_number is 1-based.
Empty pages yield empty strings but are included to preserve page numbering.
"""
from typing import List, Tuple


def extract_pdf_pages(path: str) -> List[Tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise ImportError("pypdf is required for PDF parsing") from e

    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append((i, text))
    return pages
