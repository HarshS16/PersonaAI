"""Embedding provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.ai.embeddings.base import EmbeddingProvider
from app.core.config import settings


@lru_cache
def get_embedder() -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider == "fake":
        from app.ai.embeddings.fake import FakeEmbeddingProvider

        return FakeEmbeddingProvider(dim=settings.embedding_dim)
    if provider == "fastembed":
        from app.ai.embeddings.fastembed_provider import FastEmbedProvider

        return FastEmbedProvider(model_name=settings.embedding_model, dim=settings.embedding_dim)
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


__all__ = ["get_embedder", "EmbeddingProvider"]
