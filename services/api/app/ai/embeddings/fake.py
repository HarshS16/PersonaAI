"""Deterministic hash-based embeddings for tests (no model download)."""

from __future__ import annotations

import hashlib
import math

from app.ai.embeddings.base import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        # Seed a simple PRNG from the text hash; produce a unit vector so cosine
        # similarity behaves sensibly and identical text maps to identical vectors.
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)
        vals: list[float] = []
        x = seed or 1
        for _ in range(self.dim):
            x = (1103515245 * x + 12345) & 0x7FFFFFFF
            vals.append((x / 0x7FFFFFFF) * 2 - 1)
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]
