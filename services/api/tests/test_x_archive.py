"""Tests for X/Twitter archive import."""

from __future__ import annotations

import io
import json
import uuid
import zipfile

from httpx import AsyncClient


def _make_tweets_js(tweets: list[str] | None = None) -> bytes:
    if tweets is None:
        tweets = [
            "Just shipped a new feature using FastAPI and PostgreSQL. Loving the async support!",
            "Great talk at PyCon about type hints and Pydantic v2. The future is typed.",
            "Building RAG pipelines is incredibly rewarding when the retrieval quality is high.",
        ]
    payload = [{"tweet": {"full_text": t}} for t in tweets]
    return f"window.YTD.tweets.part0 = {json.dumps(payload)}".encode()


def _make_x_archive_zip(tweets: list[str] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/tweets.js", _make_tweets_js(tweets))
    return buf.getvalue()


async def _upload(client: AsyncClient, *, use_zip: bool = True) -> dict:
    if use_zip:
        data = _make_x_archive_zip()
        filename = "x_archive.zip"
    else:
        data = _make_tweets_js()
        filename = "tweets.js"
    resp = await client.post(
        "/sources/x/upload",
        files={"file": (filename, data, "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sync(job_id: str) -> dict:
    from app.ingestion.x_sync import sync_x_job
    return await sync_x_job(uuid.UUID(job_id))


async def test_x_upload_bad_extension(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/x/upload",
        files={"file": ("data.csv", b"hello", "text/csv")},
    )
    assert resp.status_code == 400


async def test_x_archive_indexes_tweets(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    await _sync(body["job"]["id"])

    search = (await auth_client.get("/search", params={"q": "FastAPI"})).json()
    assert any("fastapi" in e["text"].lower() for e in search["excerpts"])


async def test_x_archive_computes_writing_style(auth_client: AsyncClient) -> None:
    body = await _upload(auth_client)
    await _sync(body["job"]["id"])

    style = (await auth_client.get("/persona/writing-style")).json()
    assert "avg_sentence_length" in style
    assert style["avg_sentence_length"] > 0


async def test_x_js_file_upload(auth_client: AsyncClient) -> None:
    """Can upload just the tweets.js file instead of the full ZIP."""
    body = await _upload(auth_client, use_zip=False)
    await _sync(body["job"]["id"])

    sources = (await auth_client.get("/sources")).json()
    x = next(s for s in sources if s["type"] == "x_archive")
    assert x["status"] == "synced"
    assert x["stats"]["tweets"] >= 3
