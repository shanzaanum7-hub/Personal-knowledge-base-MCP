# Architecture — Personal Knowledge-Base MCP Server

> **Status:** Phase 1 — Foundation only.
> Components marked **(planned)** are not yet implemented.

---

## 1. Overview

The system lets multiple users upload personal documents (PDF, Markdown, TXT) and
perform semantic search over their own private knowledge base.
The same retrieval capability is exposed through two interfaces:

1. A standard **FastAPI** web application consumed by the frontend.
2. A **FastMCP** server consumed by MCP-compatible AI clients.

Both interfaces reuse the same application and retrieval services. There is no
duplicate retrieval logic.

---

## 2. Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
│         React / Next.js  (Owner: Shanza)  [planned]            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────────┐
│                      FASTAPI API LAYER                          │
│         backend/app/  (Owner: Shanza)                           │
│         • POST /documents/upload     [planned]                  │
│         • GET  /search               [planned]                  │
│         • POST /auth/register        [planned]                  │
│         • POST /auth/login           [planned]                  │
│         • GET  /health               [Phase 1 — implemented]    │
└──────────────┬────────────────────────┬────────────────────────-┘
               │                        │
┌──────────────▼──────────┐  ┌──────────▼──────────────────────────┐
│  APPLICATION SERVICES   │  │      AUTHENTICATION / CORE          │
│  backend/app/services/  │  │      backend/app/core/              │
│  (Owner: Shanza)        │  │      (Owner: Afaq)  [planned]       │
│  [planned]              │  │      • JWT token handling           │
└──────────────┬──────────┘  └─────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│                   DOCUMENT PROCESSING                           │
│            backend/ingestion/   (Owner: Aliza)  [planned]       │
│            • PDF parsing  (pypdf)                               │
│            • Markdown / TXT parsing                             │
│            • Text chunking                                      │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│                     EMBEDDINGS SERVICE                          │
│            backend/embeddings/  (Owner: Samia)  [planned]       │
│            • Configurable provider (OpenAI / HuggingFace /      │
│              Cohere etc.)                                       │
│            • Provider swappable without changing retrieval       │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│                     QDRANT VECTOR DATABASE                      │
│            backend/vector_store/  (Owner: Samia)  [planned]     │
│            • Single collection, payload-filtered by user_id      │
│            • Each chunk payload:                                │
│              {                                                  │
│                "user_id":  "user_123",                          │
│                "doc_id":   "doc_001",                           │
│                "filename": "AI_Notes.pdf",                      │
│                "page":     5,                                   │
│                "chunk_id": 12,                                  │
│                "text":     "..."                                │
│              }                                                  │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│                    RETRIEVAL SERVICE                            │
│            backend/retrieval/  (Owner: Samia)  [planned]        │
│            • Embed query                                        │
│            • Filter by authenticated user_id                    │
│            • Return top-k ranked chunks                         │
└──────────────┬──────────────────────────────────────────────────┘
               │
        (shared service layer — no duplication)
               │
┌──────────────▼──────────────────────────────────────────────────┐
│                      FASTMCP SERVER                             │
│            backend/mcp/  (Owner: Shanza)  [planned]             │
│            • Wraps the same retrieval service                   │
│            • Exposes MCP tools (e.g. search_knowledge_base)     │
└──────────────┬──────────────────────────────────────────────────┘
               │ MCP protocol
┌──────────────▼──────────────────────────────────────────────────┐
│                       MCP CLIENT                                │
│            Any MCP-compatible AI client / IDE plugin [planned]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Details

### 3.1 Frontend (planned)

| Detail | Value |
|--------|-------|
| Owner | Shanza |
| Technology | React or Next.js |
| Location | `frontend/` |
| Responsibilities | Document upload UI, search interface, authentication forms |
| Talks to | FastAPI via HTTP/REST |

### 3.2 FastAPI API Layer

| Detail | Value |
|--------|-------|
| Owner | Shanza |
| Technology | Python, FastAPI, Uvicorn |
| Location | `backend/app/` |
| Phase 1 status | `GET /health` implemented |
| CORS | Configurable via `FRONTEND_ORIGIN` environment variable |

### 3.3 Document Processing (planned)

| Detail | Value |
|--------|-------|
| Owner | Aliza |
| Technology | pypdf, Python stdlib |
| Location | `backend/ingestion/` |
| Responsibilities | Parse PDF, Markdown, TXT; split into chunks with metadata |

### 3.4 Embeddings Service (planned)

| Detail | Value |
|--------|-------|
| Owner | Samia |
| Technology | Configurable — provider set via `EMBEDDING_PROVIDER` env var |
| Location | `backend/embeddings/` |
| Design requirement | Provider must be replaceable without changing retrieval logic |

### 3.5 Qdrant (planned)

| Detail | Value |
|--------|-------|
| Owner | Samia |
| Technology | Qdrant, qdrant-client Python SDK |
| Location | `backend/vector_store/` |
| User isolation | Payload-based filter on `user_id` — users never see each other's data |

### 3.6 Retrieval Service (planned)

| Detail | Value |
|--------|-------|
| Owner | Samia |
| Technology | Python, qdrant-client |
| Location | `backend/retrieval/` |
| Responsibilities | Embed query, apply user_id filter, return ranked top-k results |

### 3.7 FastMCP Server (planned)

| Detail | Value |
|--------|-------|
| Owner | Shanza |
| Technology | FastMCP |
| Location | `backend/mcp/` |
| Key constraint | Must reuse the same retrieval/application services as the FastAPI layer — no duplicate logic |

### 3.8 MCP Client (planned)

Any MCP-compatible client (IDE plugin, Claude desktop, custom tool) can connect to
the FastMCP server and invoke retrieval tools once Phase 2+ is implemented.

---

## 4. Planned Data Flow

### Document Ingestion Flow (planned)

```
User uploads file via Frontend
  → POST /documents/upload (FastAPI)
  → Authentication check (JWT)
  → Document parsing (ingestion service)
  → Text chunking
  → Embed chunks (embeddings service)
  → Store vectors + payload in Qdrant (vector_store service)
```

### Search Flow (planned)

```
User submits query via Frontend
  → GET /search?q=... (FastAPI)
  → Authentication — extract user_id from JWT
  → Embed query (embeddings service)
  → Vector search filtered by user_id (retrieval service)
  → Return ranked chunks to frontend
```

### MCP Search Flow (planned)

```
MCP Client calls tool: search_knowledge_base(query, user_id)
  → FastMCP server
  → Same retrieval service (no duplication)
  → Same Qdrant collection
  → Return ranked chunks to MCP client
```

---

## 5. Security Model

- Every request is authenticated via JWT.
- The `user_id` extracted from the JWT is injected into every Qdrant query as a
  payload filter. It is never accepted from the client.
- A user can only read, update, or delete their own documents.
- This is implemented in Phase 2 (authentication owner: Afaq).

---

## 6. Configuration

All sensitive values and environment-specific settings are loaded from environment
variables (or a local `.env` file). See `.env.example` for the full list.
The settings object is defined in `backend/app/core/config.py` using
`pydantic-settings`.

---

*Document last updated: Phase 1*
