"""Document API routes.

POST /documents/upload
    Ingest an uploaded PDF, TXT, or Markdown document.

GET /documents
    List documents belonging to the authenticated user.

User isolation is enforced by extracting user_id exclusively
from the JWT. The client cannot supply or override user_id.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.app.core.security import CurrentUserId
from backend.app.models.document import DocumentMeta, UploadResponse
from backend.app.services.document_service import DocumentService
from backend.ingestion.ingest import IngestionError


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


# ---------------------------------------------------------------------------
# Supported document formats
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


def _get_document_service() -> DocumentService:
    """FastAPI dependency that returns a DocumentService instance.

    Tests can override this dependency using app.dependency_overrides.
    """
    return DocumentService()


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document",
    responses={
        201: {
            "description": "Document ingested and stored successfully."
        },
        400: {
            "description": (
                "Invalid file type, missing filename, empty file, "
                "or ingestion error."
            )
        },
        401: {
            "description": "Missing or invalid authentication token."
        },
        422: {
            "description": "Validation error."
        },
        500: {
            "description": "Internal ingestion, embedding, or storage error."
        },
    },
)
async def upload_document(
    user_id: CurrentUserId,
    file: UploadFile | None = File(
        None,
        description="PDF, TXT, or Markdown file to ingest.",
    ),
    service: DocumentService = Depends(_get_document_service),
) -> UploadResponse:
    """Ingest an uploaded document for the authenticated user.

    The user_id is obtained exclusively from the JWT token.
    The client cannot provide or override the user_id.

    The document is:
        1. Parsed
        2. Cleaned
        3. Chunked
        4. Embedded
        5. Stored in Qdrant
    """

    # FastAPI will give None when the upload does not contain
    # a usable filename/file part.
    if file is None or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided with the upload.",
        )

    # Validate the file extension before calling the service.
    # Only PDF, TXT, and Markdown documents are supported.
    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file type. "
                "Only PDF, TXT, and Markdown files are supported."
            ),
        )

    try:
        result = await service.ingest_upload(
            file=file,
            user_id=user_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingestion failed: {exc}",
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An internal error occurred while processing the document. "
                "Please try again later."
            ),
        ) from exc

    return result


# ---------------------------------------------------------------------------
# GET /documents
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[DocumentMeta],
    status_code=status.HTTP_200_OK,
    summary="List the authenticated user's documents",
    responses={
        200: {
            "description": (
                "List of documents belonging to the authenticated user."
            )
        },
        401: {
            "description": "Missing or invalid authentication token."
        },
        500: {
            "description": "Internal error while listing documents."
        },
    },
)
def list_documents(
    user_id: CurrentUserId,
    service: DocumentService = Depends(_get_document_service),
) -> list[DocumentMeta]:
    """Return documents belonging only to the authenticated user.

    The user_id comes from the JWT token, ensuring that users
    cannot access another user's documents.
    """

    try:
        return service.list_documents(
            user_id=user_id,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An internal error occurred while listing documents. "
                "Please try again later."
            ),
        ) from exc