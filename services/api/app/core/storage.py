"""File storage behind a small interface. Local filesystem in dev; an S3
adapter can be slotted in for production without touching call sites.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, *, key_prefix: str, filename: str) -> str:
        safe = filename.replace("/", "_").replace("\\", "_")
        rel = f"{key_prefix}/{uuid.uuid4().hex}_{safe}"
        path = self.base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return rel

    def read(self, rel: str) -> bytes:
        return (self.base / rel).read_bytes()

    def delete(self, rel: str) -> None:
        import contextlib

        with contextlib.suppress(FileNotFoundError):
            (self.base / rel).unlink()

    def delete_prefix(self, prefix: str) -> None:
        """Remove an entire key prefix directory (e.g. all of a persona's files)."""
        import shutil

        target = self.base / prefix
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)


def get_storage() -> LocalStorage:
    # Only local is implemented for the MVP; S3 adapter is a later addition.
    return LocalStorage(settings.storage_local_dir)
