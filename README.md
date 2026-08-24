# Personal Knowledge-Base MCP Server

> AI/GenAI Fellowship Project — Phase 1 (Foundation)

# Personal Knowledge-Base (MCP-compatible)

Concise demo project: a multi-user personal knowledge-base focused on
semantic retrieval (not an LLM-answering chatbot). The system exposes a
FastAPI backend, a minimal frontend (vanilla HTML/JS), and a FastMCP toolset
so IDEs or MCP-aware clients can call the same retrieval logic.

What follows is a short, recruiter-friendly summary and exact run / test notes
based only on what's implemented and verified in this repository.

---

**Problem**
- Personal documents (PDF/TXT/MD) are hard to search at passage-level across a
	cross-device personal corpus. This project demonstrates per-user semantic
	retrieval over indexed text chunks.

**What the project does**
- Allows users to register/login (JWT), ingest documents (ingestion helpers),
	index embeddings into Qdrant, and perform semantic search scoped to their
	account. The same retrieval logic is exposed via REST and MCP tools.

**Architecture (short)**
- Frontend (vanilla HTML/JS) → FastAPI app (backend/app) → Ingestion →
	Embeddings → Qdrant (vector DB) → Retrieval service → Frontend / MCP client

**Tech stack (implemented / used here)**
- FastAPI, Uvicorn
- FastMCP (tools hosted and mounted by the FastAPI app)
- Qdrant (vector DB, external service)
- Embeddings: configurable provider (OpenAI / local models supported by code)
- Authentication: JWT (`python-jose`) + bcrypt password hashing (`passlib`)
- Document parsing: code under `backend/ingestion/` (PDF + text chunking)

**Authentication and per-user isolation**
- Users register via `POST /auth/register`, login via `POST /auth/login`.
- Tokens are JWTs whose subject is the `user_id`. The backend extracts the
	`user_id` from the token for all user-scoped operations (see `CurrentUserId`).
- Qdrant payloads and retrieval filters include `user_id` so searches and
	document listings are restricted to the authenticated user.

**Ingestion → embeddings → Qdrant → retrieval flow (short)**
- Ingestion helpers: `backend/ingestion/ingest.py` detects file types,
	parses pages/text, cleans and chunks content.
- Embeddings abstraction: `backend/embeddings/` (configurable providers).
- Vector store: `backend/vector_store/qdrant_service.py` wraps Qdrant client.
- Retrieval: `backend/retrieval/retrieval_service.py` performs similarity search
	and applies a confidence threshold; returned chunks include source metadata.

**MCP tools (available)**
- `search_notes(query, user_id, top_k)` — semantic search, returns ranked chunks
- `get_document(doc_id, user_id)` — returns stored chunks for a single document
- `list_sources(user_id)` — list documents owned by the user

These tools are defined in `backend/mcp/server.py` and reuse the same
DocumentService / RetrievalService as the REST API.

---

## Setup (quick)

1. Create and activate a Python 3.11+ virtualenv

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

3. Start a Qdrant instance (local Docker example)

```powershell
docker run -p 6333:6333 qdrant/qdrant:latest
```

4. Copy and edit environment variables

```powershell
copy .env.example .env
# edit .env with your values (JWT secret, Qdrant URL/collection, embedding keys)
```

Minimum environment variables (see `.env.example`):
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_USERS_JSON` (can be `{}` for an empty user set)
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
- `EMBEDDING_PROVIDER` and provider-specific keys (e.g. `OPENAI_API_KEY`)

---

## How to run the backend

Run the FastAPI app (it mounts the MCP server at `/mcp`):

```powershell
uvicorn backend.app.main:app --reload
```

- API docs: http://localhost:8000/docs
- Health: `GET /health` (returns `{"status":"ok"}`)

You can also run the MCP server standalone for local testing:

```powershell
python -m backend.mcp.server
```

---

## How to run the frontend

- The frontend is a minimal static demo in `frontend/index.html` and `frontend/js`.
- After starting the backend, open `frontend/index.html` in your browser.
- Ensure `FRONTEND_ORIGIN` in `.env` includes the origin you use to open the
	static page (for local file testing, set `FRONTEND_ORIGIN=http://localhost:*/`).

Note: the demo is intentionally simple (no build step). For a production
frontend, serve the files with a static server or integrate with a React app.

---

## How to connect / test MCP and REST

Authentication:
- Register: `POST /auth/register` with JSON `{ "username": "alice", "password": "..." }`
- Login: `POST /auth/login` (OAuth2 form) to receive `access_token` (Bearer).

Example: search via REST (replace <TOKEN>):

```bash
curl -X POST http://localhost:8000/search \\
	-H "Authorization: Bearer <TOKEN>" \\
	-H "Content-Type: application/json" \\
	-d '{"query":"your question","top_k":5}'
```

MCP tools (two options):
- Run the MCP server standalone (`python -m backend.mcp.server`) and use an
	MCP-aware client to call `search_notes`, `get_document`, or `list_sources`.
- Or run the FastAPI app (which mounts the MCP HTTP app at `/mcp`) and call
	the mounted MCP endpoints from a client compatible with FastMCP HTTP.

Refer to `backend/mcp/server.py` for the exact tool signatures.

---

## Evaluation (what was run here)

- A tiny benchmark runner exists at `evaluation/run_benchmark.py` and expects a
	dataset of queries + expected document IDs (see `evaluation/benchmark_dataset.json`).
- For demonstration, a minimal adapter `evaluation/adapter_simple.py` was added
	that returns the placeholder doc id in the sample dataset. Running the
	benchmark with that adapter produced:

```json
{"queries": 1, "hit_rate": 1.0, "mrr": 1.0}
```

- Important: this result is artificial — the dataset in the repo is a
	placeholder and the adapter returns the expected document ID. To obtain
	meaningful metrics, provide a representative dataset and an adapter that
	queries the real retrieval stack (see `evaluation/run_benchmark.py`).

Command used to reproduce the demo run:

```powershell
python -m evaluation.run_benchmark evaluation/benchmark_dataset.json --search evaluation.adapter_simple:simple_search --top-k 10
```

---

## Demo quick walk-through

1. Start Qdrant and the backend (see Setup + How to run the backend).
2. Open `frontend/index.html` in your browser.
3. Register a new user (Register form) and the demo will perform an auto-login.
4. Ingest documents either by:
	 - using the ingestion helpers (`backend/ingestion/ingest_document`) or
	 - calling the REST upload endpoint (`POST /documents/upload`) if you wire a
		 client to send files.
5. Use the Search box to run natural-language queries scoped to the logged-in
	 user; open document modals to view indexed chunks (demo UI uses filename
	 scoped search to fetch chunks).

---

## Notes & current limitations (verified)
- `POST /auth/register` stores users in the running process's `AUTH_USERS_JSON`
	(in-memory) — it's suitable for demos but not for production persistence.
- Some end-to-end features require a running Qdrant instance and valid
	embedding provider credentials to index and search real documents.
- Tests that require external packages or services may not run until the
	environment dependencies (Qdrant, embedding provider) are available.

---

If you'd like, I can:
- add a small adapter that calls the running `/search` endpoint for an
	end-to-end evaluation, or
- add a tiny representative benchmark dataset and a script to ingest its
	documents into Qdrant so the evaluation measures the real retrieval stack.

That's it — let me know which follow-up you'd prefer.

