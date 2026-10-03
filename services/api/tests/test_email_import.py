"""Tests for email import connector."""

from __future__ import annotations

from httpx import AsyncClient


async def test_email_upload_bad_extension(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/email/upload",
        files={"file": ("data.csv", b"some,csv,data", "text/csv")},
    )
    assert resp.status_code == 400


async def test_email_upload_empty(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/email/upload",
        files={"file": ("mail.mbox", b"", "application/mbox")},
    )
    assert resp.status_code == 400
