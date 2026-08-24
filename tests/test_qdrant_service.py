from types import SimpleNamespace

import pytest

from backend.app.core.config import Settings
from backend.ingestion.schemas import Chunk
from backend.vector_store.qdrant_service import (
    QdrantService,
    SearchResult,
    VectorStoreConnectionError,
    VectorStoreValidationError,
)


class FakeQdrant:
    def __init__(self, exists=False, error=None, scroll_points=None):
        self.exists = exists
        self.error = error
        self.created = []
        self.upserted = []
        self.search_calls = []
        self.delete_calls = []
        self.scroll_calls = []
        self.scroll_points = (
            scroll_points
            if scroll_points is not None
            else [SimpleNamespace(id="p1", payload={})]
        )

    def collection_exists(self, collection_name):
        if self.error:
            raise self.error
        return self.exists

    def create_collection(self, **kwargs):
        self.created.append(kwargs)
        self.exists = True
        return True

    def upsert(self, **kwargs):
        self.upserted.append(kwargs)
        return SimpleNamespace()

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return [
            SimpleNamespace(
                score=0.95,
                payload={
                    "user_id": "user-1",
                    "doc_id": "doc-1",
                    "filename": "notes.md",
                    "page": None,
                    "chunk_id": 0,
                    "text": "stored text",
                },
            )
        ]

    def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        return (self.scroll_points, None)

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        return SimpleNamespace()


def make_service(client, vector_size=None):
    return QdrantService(
        settings=Settings(qdrant_url="http://qdrant.test", qdrant_collection="study_notes"),
        client=client,
        vector_size=vector_size,
    )


def test_initialize_creates_collection_with_dimension():
    client = FakeQdrant()

    make_service(client).initialize(vector_size=3)

    assert client.created[0]["collection_name"] == "study_notes"
    assert client.created[0]["vectors_config"].size == 3


def test_initialize_does_not_recreate_existing_collection():
    client = FakeQdrant(exists=True)

    make_service(client, vector_size=3).initialize()

    assert client.created == []


def test_upsert_preserves_payload_and_uses_stable_id():
    client = FakeQdrant()
    chunk = Chunk("doc-1", "notes.md", None, 0, "stored text")

    make_service(client).upsert_vectors("user-1", [chunk], [[0.1, 0.2]])

    point = client.upserted[0]["points"][0]
    assert point.id == make_service(FakeQdrant())._stable_point_id("user-1", "doc-1", 0)
    assert point.payload == {
        "user_id": "user-1",
        "doc_id": "doc-1",
        "filename": "notes.md",
        "page": None,
        "chunk_id": 0,
        "text": "stored text",
    }


def test_search_applies_user_filter_and_converts_results():
    client = FakeQdrant()
    result = make_service(client, vector_size=2).search([0.1, 0.2], "user-1", top_k=5)

    assert result == [SearchResult(0.95, "stored text", "doc-1", "notes.md", None, 0)]
    call = client.search_calls[0]
    assert call["limit"] == 5
    condition = call["query_filter"].must[0]
    assert condition.key == "user_id"
    assert condition.match.value == "user-1"


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k_is_rejected(top_k):
    with pytest.raises(VectorStoreValidationError):
        make_service(FakeQdrant(), vector_size=2).search([0.1, 0.2], "user-1", top_k)


def test_dimension_mismatch_is_rejected():
    with pytest.raises(VectorStoreValidationError, match="does not match"):
        make_service(FakeQdrant(), vector_size=3).upsert_vectors(
            "user-1", [Chunk("doc-1", "notes.md", None, 0, "text")], [[0.1, 0.2]]
        )


def test_qdrant_errors_are_wrapped():
    with pytest.raises(VectorStoreConnectionError, match="initialize"):
        make_service(FakeQdrant(error=ConnectionError("offline")), vector_size=2).initialize()


def test_empty_vectors_are_rejected():
    with pytest.raises(VectorStoreValidationError, match="must not be empty"):
        make_service(FakeQdrant()).upsert_vectors(
            "user-1", [Chunk("doc-1", "notes.md", None, 0, "text")], [[]]
        )


def test_delete_document_points_success():
    client = FakeQdrant(scroll_points=[SimpleNamespace(id="p1", payload={})])
    service = make_service(client)

    result = service.delete_document_points("user-1", "doc-1")

    assert result is True
    assert len(client.delete_calls) == 1
    call = client.delete_calls[0]
    conditions = call["points_selector"].must
    assert len(conditions) == 2
    assert conditions[0].key == "user_id" and conditions[0].match.value == "user-1"
    assert conditions[1].key == "doc_id" and conditions[1].match.value == "doc-1"


def test_delete_document_points_non_existent():
    client = FakeQdrant(scroll_points=[])
    service = make_service(client)

    result = service.delete_document_points("user-1", "non-existent")

    assert result is False
    assert len(client.delete_calls) == 0