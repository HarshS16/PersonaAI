"""Blog connector: ingest articles from RSS feeds (Medium, Hashnode, Dev.to, or
any RSS URL). Articles become searchable documents and feed writing-style
analysis.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("blog")

MAX_ARTICLES = 25
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\n{3,}")


@dataclass
class Article:
    title: str
    url: str
    content: str
    published: str | None = None


@dataclass
class BlogData:
    provider: str
    handle: str
    feed_url: str
    title: str | None = None
    articles: list[Article] = field(default_factory=list)


def resolve_feed_url(provider: str, handle: str) -> str:
    handle = handle.strip().lstrip("@")
    if provider == "medium":
        return f"https://medium.com/feed/@{handle}"
    if provider == "devto":
        return f"https://dev.to/feed/{handle}"
    if provider == "hashnode":
        if handle.startswith("http"):
            return handle
        host = handle if "." in handle else f"{handle}.hashnode.dev"
        return f"https://{host}/rss.xml"
    # generic RSS: the handle is the feed URL
    return handle


def _strip_html(raw: str) -> str:
    text = _TAG.sub(" ", raw)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(a, b)
    return _WS.sub("\n\n", re.sub(r"[ \t]+", " ", text)).strip()


class BlogClient(ABC):
    @abstractmethod
    async def fetch(self, *, provider: str, handle: str) -> BlogData: ...


class RealBlogClient(BlogClient):
    async def fetch(self, *, provider: str, handle: str) -> BlogData:
        import asyncio

        feed_url = resolve_feed_url(provider, handle)

        def _parse() -> BlogData:
            import feedparser

            parsed = feedparser.parse(feed_url)
            articles: list[Article] = []
            for entry in parsed.entries[:MAX_ARTICLES]:
                body = ""
                if entry.get("content"):
                    body = entry["content"][0].get("value", "")
                body = body or entry.get("summary", "") or entry.get("description", "")
                content = _strip_html(body)
                if not content:
                    continue
                articles.append(
                    Article(
                        title=entry.get("title", "Untitled"),
                        url=entry.get("link", feed_url),
                        content=content[:12000],
                        published=entry.get("published"),
                    )
                )
            return BlogData(
                provider=provider,
                handle=handle,
                feed_url=feed_url,
                title=parsed.feed.get("title") if parsed.feed else None,
                articles=articles,
            )

        return await asyncio.to_thread(_parse)


class FakeBlogClient(BlogClient):
    async def fetch(self, *, provider: str, handle: str) -> BlogData:
        return BlogData(
            provider=provider,
            handle=handle,
            feed_url=resolve_feed_url(provider, handle),
            title=f"{handle}'s blog",
            articles=[
                Article(
                    title="Building a RAG pipeline",
                    url="https://example.com/rag",
                    content="In this post I walk through building a RAG pipeline with "
                    "Python, LangChain and PostgreSQL. We cover chunking, embeddings and "
                    "retrieval. I've been writing a lot about retrieval-augmented generation.",
                    published="2026-01-01",
                ),
                Article(
                    title="Why I love FastAPI",
                    url="https://example.com/fastapi",
                    content="FastAPI makes building Python APIs a joy. Here's how I structure "
                    "services with FastAPI, Pydantic and async SQLAlchemy.",
                    published="2026-02-01",
                ),
            ],
        )


def get_blog_client() -> BlogClient:
    if settings.environment.lower() == "test":
        return FakeBlogClient()
    return RealBlogClient()
