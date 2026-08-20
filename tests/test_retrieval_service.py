from types import SimpleNamespace

import pytest

from backend.retrieval.retrieval_service import (
    NO_CONFIDENT_MATCH_MESSAGE,
    NO_RESULTS_MESSAGE,
    RetrievedResult,
    RetrievalDependencyError,
    RetrievalService,
    RetrievalValidationError,
)
from backend.vector_store.qdrant_service import SearchResult


class FakeEmbeddingService:
    def __init__(self, vector=None, error=None):
        self.vector = vector or [0.1, 0.2]
        self.error = error
        self.queries = []

    def embed_text(self, text):
        self.queries.append(text)
        if self.error:
            raise self.error
        return self.vector


class FakeVectorStore:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, query_vector, user_id, top_k):
        self.calls.append((query_vector, user_id, top_k))
        if self.error:
            raise self.error
        return self.results


def result(score, doc_id="doc", chunk_id=0):
    return SearchResult(score, f"text-{chunk_id}", doc_id, "notes.md", 2, chunk_id)


def service(embedding=None, store=None, threshold=0.70, max_top_k=50):
    return RetrievalService(
        embedding_service=embedding or FakeEmbeddingService(),
        vector_store=store or FakeVectorStore(),
        similarity_threshold=threshold,
        max_top_k=max_top_k,
    )


def test_search_embeds_query_passes_user_and_top_k():
    embedding = FakeEmbeddingService([0.4, 0.5])
    store = FakeVectorStore([result(0.9)])

    response = service(embedding, store).search("find this", "user-1", 3)

    assert embedding.queries == ["find this"]
    assert store.calls == [([0.4, 0.5], "user-1", 3)]
    assert len(response.results) == 1


def test_results_are_ranked_and_citations_preserved():
    store = FakeVectorStore([result(0.72, "doc-low", 1), result(0.95, "doc-high", 4)])

    response = service(store=store).search("query", "user-1", 5)

    assert response.results == [
        RetrievedResult(0.95, "text-4", "doc-high", "notes.md", 2, 4),
        RetrievedResult(0.72, "text-1", "doc-low", "notes.md", 2, 1),
    ]
    assert response.results[0].source.doc_id == "doc-high"
    assert response.results[0].source.chunk_id == 4


def test_results_below_threshold_are_rejected():
    response = service(store=FakeVectorStore([result(0.69)])).search("query", "user-1")

    assert response.results == []
    assert response.message == NO_CONFIDENT_MATCH_MESSAGE


def test_no_result_case_has_clear_message():
    response = service().search("query", "user-1")

    assert response.results == []
    assert response.message == NO_RESULTS_MESSAGE


@pytest.mark.parametrize("query", ["", "   ", None])
def test_empty_query_is_rejected(query):
    with pytest.raises(RetrievalValidationError):
        service().search(query, "user-1")


@pytest.mark.parametrize("top_k", [0, -1, 51, 1.5, True])
def test_top_k_is_bounded(top_k):
    with pytest.raises(RetrievalValidationError):
        service().search("query", "user-1", top_k)


def test_embedding_failure_is_wrapped():
    with pytest.raises(RetrievalDependencyError, match="query embedding"):
        service(embedding=FakeEmbeddingService(error=RuntimeError("offline"))).search(
            "query", "user-1"
        )


def test_vector_store_failure_is_wrapped():
    with pytest.raises(RetrievalDependencyError, match="vector store"):
        service(store=FakeVectorStore(error=RuntimeError("offline"))).search(
            "query", "user-1"
        )