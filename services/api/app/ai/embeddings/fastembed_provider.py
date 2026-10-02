"""Local embeddings via fastembed (ONNX). No API key, no network, no cost.

The model is loaded lazily and only once per process. Embedding is CPU-bound,
so it runs in a thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

from app.ai.embeddings.base import EmbeddingProvider


@lru_cache
def _model(model_name: str):  # type: ignore[no-untyped-def]
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name)


class FastEmbedProvider(EmbeddingProvider):
    name = "fastembed"

    def __init__(self, model_name: str, dim: int) -> None:
        self.model_name = model_name
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        def _run() -> list[list[float]]:
            model = _model(self.model_name)
            return [vec.tolist() for vec in model.embed(texts)]

        return await asyncio.to_thread(_run)
