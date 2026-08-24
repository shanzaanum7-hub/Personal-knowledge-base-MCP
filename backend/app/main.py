"""
Personal Knowledge-Base MCP Server — FastAPI application entry point.

Phase 1: health check and CORS foundation.
Phase 2: authentication, document upload/listing, and semantic search API.
Phase 3: FastMCP server integration.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import get_settings
from backend.app.api.auth import router as auth_router
from backend.app.api.documents import router as documents_router
from backend.app.api.search import router as search_router
from backend.mcp.server import mcp


settings = get_settings()


# ---------------------------------------------------------------------------
# MCP application & lifespan
# ---------------------------------------------------------------------------

mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Lifespan context manager for the main FastAPI application.

    Delegates to FastMCP's lifespan context while handling duplicate
    TestClient context entries during test execution.
    """
    try:
        async with mcp_app.router.lifespan_context(app):
            yield
    except RuntimeError as exc:
        if "can only be called once" in str(exc):
            yield
        else:
            raise


# ---------------------------------------------------------------------------
# FastAPI application
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
    lifespan=app_lifespan,
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

    Missing upload files are returned as HTTP 400.
    Other validation errors remain HTTP 422.
    """

    errors = exc.errors()

    # Special handling for document upload
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

    # Normal validation errors
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
# ---------------------------------------------------------------------------

allowed_origins = [
    origin.strip()
    for origin in settings.frontend_origin.split(",")
    if origin.strip()
]

# Allow common local dev origins in addition to configured FRONTEND_ORIGIN.
# This ensures static-server setups like http://127.0.0.1:5500 and
# http://localhost:5500 are accepted during local demos without changing
# production configuration.
for _dev_origin in ("http://127.0.0.1:5500", "http://localhost:5500"):
    if _dev_origin not in allowed_origins:
        allowed_origins.append(_dev_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST API routes
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(search_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Used by local development, CI, and deployment health checks.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp_app)