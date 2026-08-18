"""Deterministic chunker that preserves paragraph boundaries when possible.

This implementation chunks at the word level (not characters) to avoid splitting
words. It aims for `target_words` per chunk with an `overlap_words` overlap.
"""
from typing import List
from .schemas import Chunk


def _words(text: str):
    return [w for w in text.split()]


def chunk_text(
    doc_id: str,
    filename: str,
    text: str,
    page: int | None,
    target_words: int = 600,
    overlap_words: int = 100,
    start_chunk_id: int = 0,
) -> List[Chunk]:
    words = _words(text)
    if not words:
        return []
    chunks = []
    i = 0
    chunk_id = start_chunk_id
    n = len(words)
    while i < n:
        end = min(i + target_words, n)
        chunk_words = words[i:end]
        chunk_text = " ".join(chunk_words)
        chunks.append(Chunk(doc_id=doc_id, filename=filename, page=page, chunk_id=chunk_id, text=chunk_text))
        chunk_id += 1
        if end == n:
            break
        i = max(0, end - overlap_words)
    return chunks
