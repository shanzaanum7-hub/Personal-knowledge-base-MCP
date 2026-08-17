"""
Personal Knowledge-Base MCP Server — FastAPI application entry point.

Phase 1: minimal application with health check and CORS.
Ingestion, embeddings, retrieval, and MCP endpoints are added in later phases.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings

settings = get_settings()

# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #

app = FastAPI(
    title=settings.app_name,
    description=(
        "Multi-user personal knowledge base with semantic search. "
        "Documents are stored as vector embeddings in Qdrant and "
        "retrieved via FastAPI and FastMCP."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --------------------------------------------------------------------------- #
# CORS
# Allow the React/Next.js frontend (default: localhost:3000) to talk to the API
# during local development. Adjust FRONTEND_ORIGIN in .env for staging/prod.
# --------------------------------------------------------------------------- #

allowed_origins = [origin.strip() for origin in settings.frontend_origin.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns a simple status payload so load balancers and CI pipelines
    can verify the service is alive.
    """
    return {"status": "ok"}
