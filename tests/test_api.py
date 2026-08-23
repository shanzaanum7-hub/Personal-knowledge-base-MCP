"""
Integration tests for the FastAPI API layer.

Covers:
- Authentication requirement on every protected endpoint
- POST /documents/upload  — success, bad file type, empty file, missing filename
- GET  /documents          — success, user isolation, empty list
- POST /search             — success, no-match, empty query, top_k validation,
                             user isolation, service errors

All external services (embedding, vector store, retrieval) are replaced with
lightweight fakes injected via app.dependency_overrides.
No live Qdrant or OpenAI connection is required.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.documents import _get_document_service
from backend.app.api.search import _get_search_service
from backend.app.models.document import ChunkInfo, DocumentMeta, UploadResponse
from backend.app.models.search import SearchResponse, SearchResult
from backend.app.services.document_service import DocumentService
from backend.app.services.search_service import SearchService
from backend.retrieval.retrieval_service import (
    RetrievalDependencyError,
    RetrievalValidationError,
)

# ---------------------------------------------------------------------------
# Helpers — JWT token generation for tests
# ---------------------------------------------------------------------------

def _make_token(user_id: str = "user_test") -> str:
    """Produce a real JWT signed with the test secret so auth passes."""
    from backend.app.core.config import Settings
    from backend.app.core.security import create_access_token

    settings = Settings(
        jwt_secret_key="test-secret-key-for-pytest-only",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )
    return create_access_token(user_id=user_id, settings=settings)


def _auth_headers(user_id: str = "user_test") -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


# ---------------------------------------------------------------------------
# Fake services
# ---------------------------------------------------------------------------

class FakeDocumentService:
    """Minimal DocumentService stand-in. Behaviour is set per-test."""

    def __init__(self) -> None:
        self.upload_result: UploadResponse | Exception = UploadResponse(
            doc_id="doc_test",
            filename="notes.txt",
            chunk_count=2,
            chunks=[
                ChunkInfo(chunk_id=0, page=None, text_preview="First chunk preview…"),
                ChunkInfo(chunk_id=1, page=None, text_preview="Second chunk preview…"),
            ],
        )
        self.list_result: list[DocumentMeta] | Exception = [
            DocumentMeta(doc_id="doc_test", filename="notes.txt"),
        ]
        # Track which user_id was used — lets us assert isolation
        self.last_upload_user_id: str | None = None
        self.last_list_user_id: str | None = None

    async def ingest_upload(self, file: Any, user_id: str) -> UploadResponse:
        self.last_upload_user_id = user_id
        if isinstance(self.upload_result, Exception):
            raise self.upload_result
        return self.upload_result

    def list_documents(self, user_id: str) -> list[DocumentMeta]:
        self.last_list_user_id = user_id
        if isinstance(self.list_result, Exception):
            raise self.list_result
        return self.list_result


class FakeSearchService:
    """Minimal SearchService stand-in. Behaviour is set per-test."""

    def __init__(self) -> None:
        self.search_result: SearchResponse | Exception = SearchResponse(
            query="test query",
            results=[
                SearchResult(
                    score=0.91,
                    text="Retrieval-augmented generation combines…",
                    filename="RAG_Notes.pdf",
                    page=4,
                    chunk_id=12,
                    doc_id="rag_notes",
                )
            ],
            message=None,
        )
        self.last_query: str | None = None
        self.last_user_id: str | None = None
        self.last_top_k: int | None = None

    def search(self, query: str, user_id: str, top_k: int = 5) -> SearchResponse:
        self.last_query = query
        self.last_user_id = user_id
        self.last_top_k = top_k
        if isinstance(self.search_result, Exception):
            raise self.search_result
        # Mirror the actual query in the response
        return SearchResponse(
            query=query,
            results=self.search_result.results,
            message=self.search_result.message,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_doc_service() -> FakeDocumentService:
    return FakeDocumentService()


@pytest.fixture()
def fake_search_service() -> FakeSearchService:
    return FakeSearchService()


@pytest.fixture()
def client(
    fake_doc_service: FakeDocumentService,
    fake_search_service: FakeSearchService,
) -> TestClient:
    """TestClient with all external service dependencies overridden."""
    app.dependency_overrides[_get_document_service] = lambda: fake_doc_service
    app.dependency_overrides[_get_search_service] = lambda: fake_search_service

    # Override the settings dependency so JWT validation uses our test secret
    from backend.app.core.config import Settings, get_settings
    test_settings = Settings(
        jwt_secret_key="test-secret-key-for-pytest-only",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


# Shorthand auth headers using the same test secret
AUTH = _make_token.__wrapped__ if hasattr(_make_token, "__wrapped__") else None


def auth(user_id: str = "user_test") -> dict[str, str]:
    from backend.app.core.config import Settings
    from backend.app.core.security import create_access_token
    settings = Settings(
        jwt_secret_key="test-secret-key-for-pytest-only",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )
    token = create_access_token(user_id=user_id, settings=settings)
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# POST /documents/upload
# ===========================================================================

class TestUploadDocument:

    def test_upload_txt_returns_201(
        self, client: TestClient, fake_doc_service: FakeDocumentService
    ) -> None:
        """Valid TXT upload returns 201 with correct payload."""
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("notes.txt", b"Hello knowledge base.", "text/plain")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["doc_id"] == "doc_test"
        assert body["filename"] == "notes.txt"
        assert body["chunk_count"] == 2
        assert len(body["chunks"]) == 2

    def test_upload_pdf_accepted(
        self, client: TestClient
    ) -> None:
        """PDF content-type is accepted without rejection at the API layer."""
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        # Service fake always succeeds — we just care it reaches the service
        assert response.status_code == 201

    def test_upload_md_accepted(
        self, client: TestClient
    ) -> None:
        """Markdown files are accepted."""
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("notes.md", b"# Title\nContent.", "text/markdown")},
        )
        assert response.status_code == 201

    def test_upload_unsupported_extension_returns_400(
        self, client: TestClient
    ) -> None:
        """Files with unsupported extensions are rejected before the service is called."""
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("malware.exe", b"\x4d\x5a", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_docx_returns_400(self, client: TestClient) -> None:
        """DOCX is not a supported format."""
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("doc.docx", b"PK fake zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert response.status_code == 400

    def test_upload_empty_file_returns_400(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """Service-raised ValueError (empty file) maps to HTTP 400."""
        fake_doc_service.upload_result = ValueError("Uploaded file is empty")
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_upload_ingestion_error_returns_400(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """IngestionError from the service maps to HTTP 400."""
        from backend.ingestion.ingest import IngestionError
        fake_doc_service.upload_result = IngestionError("Unsupported file type: bad.xyz")
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("bad.txt", b"content", "text/plain")},
        )
        assert response.status_code == 400
        assert "Ingestion failed" in response.json()["detail"]

    def test_upload_service_runtime_error_returns_500(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """Internal RuntimeError (embedding/storage failure) maps to HTTP 500."""
        fake_doc_service.upload_result = RuntimeError("Embedding API down")
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
        assert response.status_code == 500
        # Must NOT expose internal error message to caller
        assert "Embedding API down" not in response.json()["detail"]

    def test_upload_requires_authentication(self, client: TestClient) -> None:
        """Request without bearer token returns 401."""
        response = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
        assert response.status_code == 401

    def test_upload_uses_authenticated_user_id(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """The user_id forwarded to the service comes from the JWT, not the request."""
        client.post(
            "/documents/upload",
            headers=auth("specific_user_abc"),
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
        assert fake_doc_service.last_upload_user_id == "specific_user_abc"

    def test_upload_no_filename_returns_400(self, client: TestClient) -> None:
        """Missing filename in the upload is rejected with 400."""
        response = client.post(
            "/documents/upload",
            headers=auth(),
            files={"file": ("", b"content", "text/plain")},
        )
        assert response.status_code == 400


# ===========================================================================
# GET /documents
# ===========================================================================

class TestListDocuments:

    def test_list_returns_200_with_documents(
        self, client: TestClient
    ) -> None:
        """Authenticated user receives their document list."""
        response = client.get("/documents", headers=auth())
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert body[0]["doc_id"] == "doc_test"
        assert body[0]["filename"] == "notes.txt"

    def test_list_empty_returns_empty_list(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """User with no documents receives an empty list."""
        fake_doc_service.list_result = []
        response = client.get("/documents", headers=auth())
        assert response.status_code == 200
        assert response.json() == []

    def test_list_requires_authentication(self, client: TestClient) -> None:
        """Unauthenticated request returns 401."""
        response = client.get("/documents")
        assert response.status_code == 401

    def test_list_user_isolation(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """The user_id forwarded to the service comes from the JWT."""
        client.get("/documents", headers=auth("alice_42"))
        assert fake_doc_service.last_list_user_id == "alice_42"

    def test_list_different_users_get_separate_calls(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """Two users' requests are routed with their respective user IDs."""
        client.get("/documents", headers=auth("user_a"))
        assert fake_doc_service.last_list_user_id == "user_a"

        client.get("/documents", headers=auth("user_b"))
        assert fake_doc_service.last_list_user_id == "user_b"

    def test_list_service_error_returns_500(
        self,
        client: TestClient,
        fake_doc_service: FakeDocumentService,
    ) -> None:
        """RuntimeError from the service maps to HTTP 500 without leaking details."""
        fake_doc_service.list_result = RuntimeError("Qdrant is down")
        response = client.get("/documents", headers=auth())
        assert response.status_code == 500
        assert "Qdrant is down" not in response.json()["detail"]


# ===========================================================================
# POST /search
# ===========================================================================

class TestSearch:

    def test_search_returns_200_with_results(
        self, client: TestClient
    ) -> None:
        """Valid authenticated search returns 200 with ranked results."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "What is retrieval augmented generation?", "top_k": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "What is retrieval augmented generation?"
        assert isinstance(body["results"], list)
        assert len(body["results"]) == 1
        result = body["results"][0]
        assert result["score"] == 0.91
        assert result["filename"] == "RAG_Notes.pdf"
        assert result["page"] == 4
        assert result["chunk_id"] == 12

    def test_search_default_top_k(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """top_k defaults to 5 when not provided."""
        client.post(
            "/search",
            headers=auth(),
            json={"query": "some query"},
        )
        assert fake_search_service.last_top_k == 5

    def test_search_custom_top_k(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """Explicit top_k value is forwarded to the service."""
        client.post(
            "/search",
            headers=auth(),
            json={"query": "some query", "top_k": 10},
        )
        assert fake_search_service.last_top_k == 10

    def test_search_top_k_above_max_returns_422(
        self, client: TestClient
    ) -> None:
        """top_k > 50 is rejected by Pydantic validation (422)."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "test", "top_k": 51},
        )
        assert response.status_code == 422

    def test_search_top_k_zero_returns_422(
        self, client: TestClient
    ) -> None:
        """top_k = 0 is invalid."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "test", "top_k": 0},
        )
        assert response.status_code == 422

    def test_search_top_k_negative_returns_422(
        self, client: TestClient
    ) -> None:
        """Negative top_k is rejected."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "test", "top_k": -1},
        )
        assert response.status_code == 422

    def test_search_empty_query_returns_422(
        self, client: TestClient
    ) -> None:
        """Empty string query is rejected by Pydantic (min_length=1)."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "", "top_k": 5},
        )
        assert response.status_code == 422

    def test_search_whitespace_only_query_returns_422(
        self, client: TestClient
    ) -> None:
        """Whitespace-only query is rejected by the custom validator."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "   ", "top_k": 5},
        )
        assert response.status_code == 422

    def test_search_missing_query_field_returns_422(
        self, client: TestClient
    ) -> None:
        """Request body without query field is a validation error."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"top_k": 5},
        )
        assert response.status_code == 422

    def test_search_requires_authentication(self, client: TestClient) -> None:
        """Unauthenticated search request returns 401."""
        response = client.post(
            "/search",
            json={"query": "test", "top_k": 5},
        )
        assert response.status_code == 401

    def test_search_no_confident_match_returns_200_with_message(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """No-match case returns HTTP 200 (not 404) with empty results and a message."""
        from backend.retrieval.retrieval_service import NO_CONFIDENT_MATCH_MESSAGE
        fake_search_service.search_result = SearchResponse(
            query="obscure query",
            results=[],
            message=NO_CONFIDENT_MATCH_MESSAGE,
        )
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "obscure query", "top_k": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["results"] == []
        assert body["message"] == NO_CONFIDENT_MATCH_MESSAGE

    def test_search_user_isolation(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """The user_id forwarded to the service comes from the JWT, not the request."""
        client.post(
            "/search",
            headers=auth("bob_99"),
            json={"query": "test", "top_k": 5},
        )
        assert fake_search_service.last_user_id == "bob_99"

    def test_search_different_users_scoped_separately(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """Two users' searches carry their own user IDs."""
        client.post("/search", headers=auth("alice"), json={"query": "q", "top_k": 3})
        assert fake_search_service.last_user_id == "alice"

        client.post("/search", headers=auth("bob"), json={"query": "q", "top_k": 3})
        assert fake_search_service.last_user_id == "bob"

    def test_search_retrieval_validation_error_returns_400(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """RetrievalValidationError from the service maps to HTTP 400."""
        fake_search_service.search_result = RetrievalValidationError("top_k out of range")
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "test", "top_k": 5},
        )
        assert response.status_code == 400

    def test_search_retrieval_dependency_error_returns_503(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """RetrievalDependencyError (embedding/Qdrant down) maps to HTTP 503."""
        fake_search_service.search_result = RetrievalDependencyError("Qdrant unreachable")
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "test", "top_k": 5},
        )
        assert response.status_code == 503
        # Must NOT expose internal error details
        assert "Qdrant unreachable" not in response.json()["detail"]

    def test_search_query_forwarded_correctly(
        self,
        client: TestClient,
        fake_search_service: FakeSearchService,
    ) -> None:
        """The exact query string is forwarded to the service and echoed in response."""
        my_query = "What is the capital of France?"
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": my_query, "top_k": 3},
        )
        assert response.status_code == 200
        assert response.json()["query"] == my_query
        assert fake_search_service.last_query == my_query

    def test_search_result_includes_source_citation_fields(
        self, client: TestClient
    ) -> None:
        """Each result contains score, text, filename, page, chunk_id, doc_id."""
        response = client.post(
            "/search",
            headers=auth(),
            json={"query": "test", "top_k": 5},
        )
        result = response.json()["results"][0]
        for field in ("score", "text", "filename", "page", "chunk_id", "doc_id"):
            assert field in result, f"Missing field: {field}"


# ===========================================================================
# Auth endpoint (smoke tests — full auth tests in separate module)
# ===========================================================================

class TestAuthEndpoint:

    def test_login_with_bad_credentials_returns_401(
        self, client: TestClient
    ) -> None:
        """Invalid credentials return 401."""
        response = client.post(
            "/auth/login",
            data={"username": "nobody", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_protected_endpoints_reject_bad_token(
        self, client: TestClient
    ) -> None:
        """A malformed token is rejected by all protected endpoints."""
        bad_headers = {"Authorization": "Bearer this.is.not.valid"}
        for method, url, kwargs in [
            ("get", "/documents", {}),
            ("post", "/documents/upload", {"files": {"file": ("f.txt", b"x", "text/plain")}}),
            ("post", "/search", {"json": {"query": "q", "top_k": 5}}),
        ]:
            resp = getattr(client, method)(url, headers=bad_headers, **kwargs)
            assert resp.status_code == 401, f"{method.upper()} {url} should return 401"

    def test_protected_endpoints_reject_missing_token(
        self, client: TestClient
    ) -> None:
        """All protected endpoints reject requests with no Authorization header."""
        for method, url, kwargs in [
            ("get", "/documents", {}),
            ("post", "/documents/upload", {"files": {"file": ("f.txt", b"x", "text/plain")}}),
            ("post", "/search", {"json": {"query": "q", "top_k": 5}}),
        ]:
            resp = getattr(client, method)(url, **kwargs)
            assert resp.status_code == 401, f"{method.upper()} {url} should return 401"
