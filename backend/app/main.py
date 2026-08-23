"""
Personal Knowledge-Base MCP Server — FastAPI application entry point.

Phase 1: health check and CORS foundation.
Phase 2: authentication, document upload/listing, and semantic search API.
MCP server integration is added in a later phase.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import get_settings
from backend.app.api.auth import router as auth_router
from backend.app.api.documents import router as documents_router
from backend.app.api.search import router as search_router


settings = get_settings()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Request validation error handler
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle FastAPI request validation errors.

    For the document upload endpoint, a missing file/filename is treated
    as a 400 Bad Request.

    All other validation errors remain 422 Unprocessable Entity.
    """

    errors = exc.errors()

    # -----------------------------------------------------------------------
    # Special case: document upload with missing file
    # -----------------------------------------------------------------------

    if request.url.path == "/documents/upload":
        for error in errors:
            location = error.get("loc", ())

            if "file" in location:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "No filename provided with the upload."
                    },
                )

    # -----------------------------------------------------------------------
    # Normal validation errors
    # -----------------------------------------------------------------------

    safe_errors = []

    for error in errors:
        safe_errors.append(
            {
                "loc": list(error.get("loc", ())),
                "msg": str(error.get("msg", "Validation error")),
                "type": str(error.get("type", "value_error")),
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "detail": safe_errors,
        },
    )


# ---------------------------------------------------------------------------
# CORS
#
# Allow the React/Next.js frontend (default: localhost:3000) to talk to the
# API during local development. Adjust FRONTEND_ORIGIN in .env for staging/prod.
# ---------------------------------------------------------------------------

allowed_origins = [
    origin.strip()
    for origin in settings.frontend_origin.split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(auth_router)        # /auth/login
app.include_router(documents_router)   # /documents/upload, /documents
app.include_router(search_router)      # /search


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns a simple status payload so load balancers and CI pipelines
    can verify the service is alive.
    """
    return {"status": "ok"}