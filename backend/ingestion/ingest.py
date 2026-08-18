"""Ingestion pipeline entry point.

Provides `ingest_document(path, doc_id=None, **kwargs)` which returns a list of
`Chunk` objects. It detects file type by extension and routes to the proper
parser, cleaning, and chunking steps.
"""
from typing import List, Optional
import os

from .pdf_parser import extract_pdf_pages
from .text_parser import read_text_file
from .cleaner import clean_text
from .chunker import chunk_text
from .schemas import Chunk


class IngestionError(Exception):
    pass


def _doc_id_from_filename(path: str) -> str:
    base = os.path.basename(path)
    return os.path.splitext(base)[0]


def ingest_document(
    path: str,
    doc_id: Optional[str] = None,
    target_words: int = 600,
    overlap_words: int = 100,
) -> List[Chunk]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    if doc_id is None:
        doc_id = _doc_id_from_filename(path)

    lower = path.lower()
    chunks: List[Chunk] = []
    if lower.endswith(".pdf"):
        pages = extract_pdf_pages(path)
        chunk_counter = 0
        for page_num, page_text in pages:
            cleaned = clean_text(page_text)
            if not cleaned:
                # include a placeholder empty chunk to preserve page metadata (optional)
                # but do not increment the counter for empty content
                continue
            page_chunks = chunk_text(
                doc_id=doc_id,
                filename=os.path.basename(path),
                text=cleaned,
                page=page_num,
                target_words=target_words,
                overlap_words=overlap_words,
                start_chunk_id=chunk_counter,
            )
            chunks.extend(page_chunks)
            chunk_counter += len(page_chunks)
        return chunks
    elif lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".markdown"):
        text, metadata = read_text_file(path)
        cleaned = clean_text(text)
        if not cleaned:
            return []
        chunks = chunk_text(doc_id=doc_id, filename=os.path.basename(path), text=cleaned, page=None, target_words=target_words, overlap_words=overlap_words)
        return chunks
    else:
        raise IngestionError(f"Unsupported file type: {path}")
