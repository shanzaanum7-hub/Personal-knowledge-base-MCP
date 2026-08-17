# Personal Knowledge-Base MCP Server

> AI/GenAI Fellowship Project — Phase 1 (Foundation)

---

## Problem Statement

Knowledge is scattered across PDFs, notes, and articles that live on local drives
or cloud storage. Finding specific information means opening files and reading
through them manually. There is no way to ask a question and get the relevant
passage back instantly — especially across a large personal document collection.

---

## Project Goal

Build a multi-user system where each user can:

1. Upload their own PDF, Markdown, and TXT documents.
2. Perform semantic search over their personal knowledge base.
3. Receive ranked, relevant text passages — not a generated answer.

The same retrieval capability is exposed through two channels:

- A **FastAPI** web application with a React/Next.js frontend.
- A **FastMCP** server for MCP-compatible AI clients and IDE plugins.

This is **not** a chatbot. There is no autonomous agent, planning loop,
fine-tuning, or LLM answer-generation layer. The system retrieves; the user reads.

---

## High-Level Architecture

```
User
 │
 ▼
Frontend (React / Next.js)
 │
 ▼
FastAPI Backend  ──────────────────────────────────────────┐
 │                                                         │
 ▼                                                         ▼
Document Processing (ingestion)              Authentication / Core
 │                                                (JWT, Afaq)
 ▼
Embeddings (configurable provider)
 │
 ▼
Qdrant (vector database, payload-filtered by user_id)
 │
 ▼
Retrieval Service (ranked results)
 │
 ├──► FastAPI response → Frontend
 │
 └──► FastMCP Server ──► MCP Client
```

Key design rule: the MCP server and the web API share the same retrieval and
application services. There is no duplicate retrieval logic.

See [`docs/architecture.md`](docs/architecture.md) for the detailed component map
and data flow.

---

## Planned Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React or Next.js |
| API framework | FastAPI + Uvicorn |
| MCP server | FastMCP |
| Vector database | Qdrant |
| Embedding service | Configurable (OpenAI / HuggingFace / Cohere) |
| Authentication | JWT via `python-jose` |
| Document parsing | pypdf, Python stdlib |
| Testing | pytest + httpx |

---

## Team Ownership

| Area | Owner | Location |
|------|-------|----------|
| Frontend, FastAPI app, MCP server, integration | Shanza | `frontend/`, `backend/app/`, `backend/mcp/` |
| Document ingestion (PDF/MD/TXT parsing, chunking) | Aliza | `backend/ingestion/` |
| Embeddings, vector store, retrieval | Samia | `backend/embeddings/`, `backend/vector_store/`, `backend/retrieval/` |
| Authentication, core config, evaluation | Afaq | `backend/app/core/`, `evaluation/` |

---

## Project Structure

```
personal-knowledge-base-mcp/
│
├── frontend/                  # React / Next.js app (planned)
│
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entry point
│   │   ├── api/               # Route handlers (planned)
│   │   ├── core/
│   │   │   └── config.py      # Pydantic settings
│   │   ├── models/            # Pydantic request/response models (planned)
│   │   └── services/          # Application-level services (planned)
│   │
│   ├── ingestion/             # Document parsing + chunking (planned)
│   ├── embeddings/            # Embedding provider abstraction (planned)
│   ├── vector_store/          # Qdrant client + collection management (planned)
│   ├── retrieval/             # Semantic search service (planned)
│   └── mcp/                   # FastMCP server (planned)
│
├── evaluation/                # Retrieval quality benchmarks (planned)
├── sample_corpus/             # Sample documents for local testing
├── docs/
│   └── architecture.md        # Detailed architecture documentation
├── tests/
│   └── test_health.py         # Health endpoint test
│
├── .env.example               # Environment variable template
├── .gitignore
├── README.md
├── LICENSE
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- Git

### 1 — Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### 3 — Configure environment variables

```bash
# Copy the example file
cp .env.example .env
# Then open .env and fill in your values
```

### 4 — Run the FastAPI server

```bash
uvicorn backend.app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 5 — Test the health endpoint

Using curl:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

Using pytest:

```bash
pytest tests/test_health.py -v
```

---

## Current Status (Phase 1)

- [x] Project structure and package layout
- [x] FastAPI application with `GET /health`
- [x] CORS configured for local frontend development
- [x] Pydantic-based configuration (env vars / `.env`)
- [x] `requirements.txt` with pinned versions
- [x] `.env.example` with placeholder values
- [x] Architecture documentation
- [x] Health endpoint test
- [ ] Document ingestion (Phase 2 — Aliza)
- [ ] Embeddings service (Phase 2 — Samia)
- [ ] Qdrant integration (Phase 2 — Samia)
- [ ] Retrieval service (Phase 2 — Samia)
- [ ] Authentication (Phase 2 — Afaq)
- [ ] FastMCP server (Phase 2 — Shanza)
- [ ] Frontend (Phase 2 — Shanza)

---

## License

See [LICENSE](LICENSE).
