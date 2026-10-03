"""Tests for PKM (bookmarks + notes) import."""

from __future__ import annotations

from httpx import AsyncClient


async def test_bookmarks_upload_bad_extension(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.post(
        "/sources/pkm/bookmarks/upload",
        files={"file": ("data.csv", b"csv", "text/csv")},
    )
    assert resp.status_code == 400


async def test_notes_upload_bad_extension(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.post(
        "/sources/pkm/notes/upload",
        files={"file": ("data.csv", b"csv", "text/csv")},
    )
    assert resp.status_code == 400


def test_bookmark_parser() -> None:
    from app.connectors.pkm import parse_bookmarks_html

    html = b"""<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
<DT><H3>Tech</H3>
<DL><p>
<DT><A HREF="https://fastapi.tiangolo.com" ADD_DATE="1696000000">FastAPI</A>
<DT><A HREF="https://docs.python.org" ADD_DATE="1696000001" TAGS="python,docs">Python Docs</A>
</DL><p>
</DL><p>"""

    bookmarks = parse_bookmarks_html(html)
    assert len(bookmarks) == 2
    assert bookmarks[0].title == "FastAPI"
    assert "Tech" in bookmarks[0].tags
    assert "python" in bookmarks[1].tags


def test_markdown_notes_parser() -> None:
    from app.connectors.pkm import parse_markdown_notes

    md = b"""# My Learning Notes

This is about #python and #fastapi development.

## Key Concepts

- Dependency injection
- Async/await patterns
"""
    notes = parse_markdown_notes(md)
    assert len(notes) == 1
    assert notes[0].title == "My Learning Notes"
    assert "python" in notes[0].tags
