"""Embedding service for query and document text vectors."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from typing import Any, Protocol

from backend.app.core.config import Settings, get_settings


Vector = list[float]


class EmbeddingServiceError(RuntimeError):
    """Base exception for embedding configuration, provider, or response errors."""


class UnsupportedEmbeddingProviderError(EmbeddingServiceError):
    """Raised when the configured embedding provider is not implemented."""


class EmbeddingProviderError(EmbeddingServiceError):
    """Raised when the configured provider cannot generate embeddings."""


class EmbeddingClient(Protocol):
    """Minimal client contract required from an embedding provider."""

    @property
    def embeddings(self) -> Any:
        ...


class EmbeddingService:
    """Generate vectors using the provider configured in application settings.

    The optional ``client`` argument is injectable so callers and tests can
    supply a provider-compatible client without making network calls.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: EmbeddingClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client

        provider = self.settings.embedding_provider.strip().lower()
        if provider != "openai":
            raise UnsupportedEmbeddingProviderError(
                f"Unsupported embedding provider: {self.settings.embedding_provider}"
            )

    def embed_text(self, text: str) -> Vector:
        """Embed one non-empty text string and return its vector."""
        self._validate_text(text)
        return self._embed([text])[0]

    def embed_texts(self, texts: Sequence[str]) -> list[Vector]:
        """Embed texts in one provider request, preserving input order."""
        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise TypeError("texts must be a sequence of strings")
        if not texts:
            raise ValueError("texts must not be empty")
        for text in texts:
            self._validate_text(text)
        return self._embed(list(texts))

    def _embed(self, texts: list[str]) -> list[Vector]:
        client = self._get_client()
        try:
            response = client.embeddings.create(
                model=self.settings.embedding_model,
                input=texts,
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Embedding provider request failed: {exc}"
            ) from exc

        try:
            data = list(response.data)
            if len(data) != len(texts):
                raise ValueError(
                    f"provider returned {len(data)} vectors for {len(texts)} texts"
                )
            ordered_data = sorted(data, key=lambda item: item.index)
            if [item.index for item in ordered_data] != list(range(len(texts))):
                raise ValueError("provider returned invalid or duplicate vector indexes")
            vectors = [self._validate_vector(item.embedding) for item in ordered_data]
            if len({len(vector) for vector in vectors}) != 1:
                raise ValueError("provider returned vectors with inconsistent dimensions")
            return vectors
        except EmbeddingProviderError:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError(
                f"Embedding provider returned an invalid response: {exc}"
            ) from exc

    def _get_client(self) -> EmbeddingClient:
        if self._client is not None:
            return self._client
        try:
            openai_module = import_module("openai")
            openai_client = openai_module.OpenAI
        except ImportError as exc:
            raise EmbeddingProviderError(
                "OpenAI provider requires the 'openai' package to be installed"
            ) from exc
        try:
            self._client = openai_client()
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Could not initialize the OpenAI client: {exc}"
            ) from exc
        return self._client

    @staticmethod
    def _validate_text(text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("text values must be strings")
        if not text.strip():
            raise ValueError("text must not be empty")

    @staticmethod
    def _validate_vector(vector: Any) -> Vector:
        if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
            raise ValueError("embedding must be a sequence of numbers")
        if not vector:
            raise ValueError("embedding vector must not be empty")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in vector
        ):
            raise ValueError("embedding vector must contain only numbers")
        return [float(value) for value in vector]