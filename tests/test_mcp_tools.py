import json

import pytest
from types import SimpleNamespace
from fastmcp import Client

from backend.mcp import server


class FakeDoc:
    def __init__(self):
        self.doc_id = "doc-xyz"
        self.filename = "notes.pdf"


class FakeDocsResponse:
    def __init__(self):
        self.docs = [FakeDoc()]


class FakeDocumentService:
    def list_documents(self, user_id: str):
        assert user_id == "user-abc"
        return [SimpleNamespace(doc_id="doc-xyz", filename="notes.pdf")]

    def _get_vector_store(self):
        class FakeStore:
            def scroll(self, collection_name, scroll_filter, limit, with_payload):
                payload = {
                    "text": "Example chunk text",
                    "doc_id": "doc-xyz",
                    "filename": "notes.pdf",
                    "page": 1,
                    "chunk_id": 0,
                }
                return ([SimpleNamespace(payload=payload)], None)

        return FakeStore()


@pytest.mark.anyio
async def test_list_sources_tool_is_registered():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    tool_names = [tool.name for tool in tools]
    assert "list_sources" in tool_names


@pytest.mark.anyio
async def test_list_sources_returns_results(monkeypatch):
    monkeypatch.setattr(server, "_document_service", FakeDocumentService())

    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "list_sources",
            {"user_id": "user-abc"},
        )

    assert len(result) == 1
    content = result[0]
    assert hasattr(content, "text")
    data = json.loads(content.text)
    assert data["results"][0]["doc_id"] == "doc-xyz"


@pytest.mark.anyio
async def test_get_document_tool_is_registered():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    tool_names = [tool.name for tool in tools]
    assert "get_document" in tool_names


@pytest.mark.anyio
async def test_get_document_returns_chunks(monkeypatch):
    monkeypatch.setattr(server, "_document_service", FakeDocumentService())

    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "get_document",
            {"doc_id": "doc-xyz", "user_id": "user-abc"},
        )

    assert len(result) == 1
    content = result[0]
    assert hasattr(content, "text")
    data = json.loads(content.text)
    assert data["doc_id"] == "doc-xyz"
    assert isinstance(data["chunks"], list)
    assert data["chunks"][0]["text"] == "Example chunk text"
