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

        if provider not in ("openai", "local", "huggingface"):
            raise UnsupportedEmbeddingProviderError(
                f"Unsupported embedding provider: "
                f"{self.settings.embedding_provider}"
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
        """Generate embeddings using the configured provider."""
        provider = self.settings.embedding_provider.strip().lower()
        # If OpenAI is selected but no API key is configured, fall back
        # to the local provider (smallest change to make local dev work).
        if provider == "openai":
            try:
                api_key = self.settings.openai_api_key.strip()
            except Exception:
                api_key = ""
            if not api_key:
                provider = "local"

        if provider in ("local", "huggingface"):
            return self._embed_local(texts)
        return self._embed_openai(texts)

    def _embed_local(self, texts: list[str]) -> list[Vector]:
        model = self._get_local_model()

        try:
            if hasattr(model, "encode"):
                embeddings = model.encode(texts, convert_to_numpy=True)
                vectors = [self._validate_vector(vec.tolist()) for vec in embeddings]
            elif hasattr(model, "embeddings") and hasattr(model.embeddings, "create"):
                response = model.embeddings.create(
                    model=self.settings.local_embedding_model,
                    input=texts,
                )
                data = sorted(list(response.data), key=lambda item: item.index)
                vectors = [self._validate_vector(item.embedding) for item in data]
            else:
                raise ValueError("Local embedding client has no encode or embeddings interface")

            if len(vectors) != len(texts):
                raise ValueError(f"provider returned {len(vectors)} vectors for {len(texts)} texts")
            return vectors
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Local embedding provider request failed: {exc}"
            ) from exc

    def _embed_openai(self, texts: list[str]) -> list[Vector]:
        client = self._get_openai_client()

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
                    f"provider returned {len(data)} vectors "
                    f"for {len(texts)} texts"
                )

            ordered_data = sorted(
                data,
                key=lambda item: item.index,
            )

            if [item.index for item in ordered_data] != list(
                range(len(texts))
            ):
                raise ValueError(
                    "provider returned invalid or duplicate vector indexes"
                )

            vectors = [
                self._validate_vector(item.embedding)
                for item in ordered_data
            ]

            if len({len(vector) for vector in vectors}) != 1:
                raise ValueError(
                    "provider returned vectors with inconsistent dimensions"
                )

            return vectors

        except EmbeddingProviderError:
            raise

        except (AttributeError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError(
                f"Embedding provider returned an invalid response: {exc}"
            ) from exc

    def _get_local_model(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            st_module = import_module("sentence_transformers")
            SentenceTransformer = st_module.SentenceTransformer
        except ImportError as exc:
            raise EmbeddingProviderError(
                "Local provider requires the 'sentence-transformers' package to be installed"
            ) from exc

        try:
            model_name = self.settings.local_embedding_model
            self._client = SentenceTransformer(model_name)
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Could not initialize local model '{self.settings.local_embedding_model}': {exc}"
            ) from exc

        return self._client

    def _get_openai_client(self) -> EmbeddingClient:
        """Create and cache the OpenAI client using the configured API key."""

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
            api_key = self.settings.openai_api_key.strip()

            if not api_key:
                raise EmbeddingProviderError(
                    "OPENAI_API_KEY is not configured."
                )

            self._client = openai_client(
                api_key=api_key
            )

        except EmbeddingProviderError:
            raise

        except Exception as exc:
            raise EmbeddingProviderError(
                f"Could not initialize the OpenAI client: {exc}"
            ) from exc

        return self._client

    @staticmethod
    def _validate_text(text: str) -> None:
        """Validate a single text input."""

        if not isinstance(text, str):
            raise TypeError("text values must be strings")

        if not text.strip():
            raise ValueError("text must not be empty")

    @staticmethod
    def _validate_vector(vector: Any) -> Vector:
        """Validate and normalize an embedding vector."""

        if isinstance(vector, (str, bytes)) or not isinstance(
            vector, Sequence
        ):
            raise ValueError(
                "embedding must be a sequence of numbers"
            )

        if not vector:
            raise ValueError(
                "embedding vector must not be empty"
            )

        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            for value in vector
        ):
            raise ValueError(
                "embedding vector must contain only numbers"
            )

        return [float(value) for value in vector]