import pytest
from fastmcp import Client

from backend.mcp import server


class FakeResult:
    def __init__(self):
        self.score = 0.92
        self.text = "CPU scheduling determines how processes are selected for execution."
        self.doc_id = "doc-123"
        self.filename = "os-notes.pdf"
        self.page = 5
        self.chunk_id = 2


class FakeResponse:
    def __init__(self):
        self.results = [FakeResult()]
        self.message = None


class FakeRetrievalService:
    def search_notes(self, query: str, user_id: str, top_k: int = 10):
        assert query == "CPU Scheduling"
        assert user_id == "user-123"
        assert top_k == 5

        return FakeResponse()


@pytest.mark.anyio
async def test_search_notes_tool_is_registered():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    tool_names = [tool.name for tool in tools]

    assert "search_notes" in tool_names


@pytest.mark.anyio
async def test_search_notes_tool_returns_results(monkeypatch):
    monkeypatch.setattr(
        server,
        "_retrieval_service",
        FakeRetrievalService(),
    )

    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "search_notes",
            {
                "query": "CPU Scheduling",
                "user_id": "user-123",
                "top_k": 5,
            },
        )

    assert len(result) == 1

    content = result[0]

    assert hasattr(content, "text")

    import json

    data = json.loads(content.text)

    assert data["results"][0]["score"] == 0.92
    assert (
        data["results"][0]["text"]
        == "CPU scheduling determines how processes are selected for execution."
    )
    assert data["results"][0]["filename"] == "os-notes.pdf"
    assert data["results"][0]["page"] == 5
    assert data["results"][0]["chunk_id"] == 2
    assert data["results"][0]["doc_id"] == "doc-123"
    assert data["message"] is None