Personal Knowledge-Base — Ingestion module

Responsibilities:
- Parse input documents (.txt, .md, .pdf)
- Chunk large documents into overlapping text slices

Phase 1 notes:
- PDF parsing uses `pypdf` if available; avoid PDFs locally if `pypdf` is not installed.
- This package intentionally provides a minimal, dependency-light API for other
  services to import: `parse_file` and `chunk_text`.

Example:

from backend.ingestion import parse_file, chunk_text

text, meta = parse_file('sample.txt')
chunks = chunk_text(text, chunk_size=1000, overlap=200)
