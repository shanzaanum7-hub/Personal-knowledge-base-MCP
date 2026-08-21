from types import SimpleNamespace

import pytest

from backend.app.core.config import Settings
from backend.embeddings.embedding_service import (
    EmbeddingProviderError,
    EmbeddingService,
)


class FakeEmbeddings:
    def __init__(self, vectors=None, error=None):
        self.vectors = vectors or []
        self.error = error
        self.calls = []

    def create(self, *, model, input):
        self.calls.append((model, input))
        if self.error:
            raise self.error
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=vector)
                for index, vector in self.vectors
            ]
        )


class FakeClient:
    def __init__(self, vectors=None, error=None):
        self.embeddings = FakeEmbeddings(vectors, error)


def service(client):
    settings = Settings(embedding_provider="openai", embedding_model="test-model")
    return EmbeddingService(settings=settings, client=client)


def test_embed_text_returns_vector_and_uses_configured_model():
    client = FakeClient([(0, [0.1, 0.2])])

    result = service(client).embed_text("hello")

    assert result == [0.1, 0.2]
    assert client.embeddings.calls == [("test-model", ["hello"])]


def test_embed_texts_preserves_input_order():
    client = FakeClient([(1, [0.2, 0.3]), (0, [0.1, 0.2])])

    result = service(client).embed_texts(["first", "second"])

    assert result == [[0.1, 0.2], [0.2, 0.3]]
    assert client.embeddings.calls == [("test-model", ["first", "second"])]


@pytest.mark.parametrize("method, value", [("embed_text", "   "), ("embed_texts", [])])
def test_empty_input_is_rejected(method, value):
    with pytest.raises(ValueError):
        getattr(service(FakeClient()), method)(value)


def test_invalid_input_is_rejected():
    with pytest.raises(TypeError):
        service(FakeClient()).embed_texts(["valid", 42])


def test_provider_errors_are_wrapped():
    client = FakeClient(error=RuntimeError("service unavailable"))

    with pytest.raises(EmbeddingProviderError, match="request failed"):
        service(client).embed_text("hello")


def test_inconsistent_vector_dimensions_are_rejected():
    client = FakeClient([(0, [0.1, 0.2]), (1, [0.3])])

    with pytest.raises(EmbeddingProviderError, match="inconsistent dimensions"):
        service(client).embed_texts(["first", "second"])