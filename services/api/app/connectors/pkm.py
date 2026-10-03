"""Personal Knowledge Management parsers: bookmarks & markdown notes."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

from app.core.errors import AppError

MAX_BOOKMARKS = 2000
MAX_NOTES = 200
MAX_NOTE_CHARS = 5000

_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]{1,30})")


# ── Bookmarks ──────────────────────────────────────────────────────


@dataclass
class Bookmark:
    title: str
    url: str
    tags: list[str] = field(default_factory=list)
    add_date: str | None = None


class _BookmarkParser(HTMLParser):
    """Parse Netscape-format bookmark HTML exports."""

    def __init__(self) -> None:
        super().__init__()
        self.bookmarks: list[Bookmark] = []
        self._folders: list[str] = []
        self._current_attrs: dict[str, str] = {}
        self._in_a = False
        self._in_h3 = False
        self._text: list[str] = []

    # ── handler callbacks ──

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr_map = {k.upper(): (v or "") for k, v in attrs}
        if tag.lower() == "a" and "HREF" in attr_map:
            self._in_a = True
            self._current_attrs = attr_map
            self._text = []
        elif tag.lower() == "h3":
            self._in_h3 = True
            self._text = []
        elif tag.lower() == "dl":
            pass  # nesting handled by h3/dt structure
        elif tag.lower() == "dt":
            pass

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._in_a:
            self._in_a = False
            title = "".join(self._text).strip()
            href = self._current_attrs.get("HREF", "")
            add_date = self._current_attrs.get(
                "ADD_DATE"
            ) or None
            tags_str = self._current_attrs.get("TAGS", "")
            tags = [
                t.strip()
                for t in tags_str.split(",")
                if t.strip()
            ]
            if self._folders:
                folder = self._folders[-1]
                if folder and folder not in tags:
                    tags.append(folder)
            if href and len(self.bookmarks) < MAX_BOOKMARKS:
                self.bookmarks.append(
                    Bookmark(
                        title=title or href,
                        url=href,
                        tags=tags,
                        add_date=add_date,
                    )
                )
            self._current_attrs = {}
        elif tag.lower() == "h3" and self._in_h3:
            self._in_h3 = False
            folder_name = "".join(self._text).strip()
            self._folders.append(folder_name)
        elif tag.lower() == "dl" and self._folders:
            self._folders.pop()

    def handle_data(self, data: str) -> None:
        if self._in_a or self._in_h3:
            self._text.append(data)


def parse_bookmarks_html(data: bytes) -> list[Bookmark]:
    """Parse a browser bookmark export HTML file."""
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as exc:
        raise AppError(
            "Cannot decode bookmark file", code="bad_encoding"
        ) from exc

    parser = _BookmarkParser()
    parser.feed(text)

    if not parser.bookmarks:
        raise AppError(
            "No bookmarks found in the file",
            code="no_bookmarks",
        )
    return parser.bookmarks


# ── Markdown Notes ─────────────────────────────────────────────────


@dataclass
class Note:
    title: str
    content: str
    tags: list[str] = field(default_factory=list)


def _extract_title(text: str, fallback: str) -> str:
    """Title from first # heading or fallback to filename."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("# ").strip()
    return fallback


def _extract_tags(text: str) -> list[str]:
    """Find #tag patterns in markdown content."""
    return list(dict.fromkeys(_TAG_RE.findall(text)))


def _parse_single_md(
    content: str, filename: str
) -> Note:
    title = _extract_title(
        content, filename.rsplit(".", 1)[0]
    )
    tags = _extract_tags(content)
    truncated = content[:MAX_NOTE_CHARS]
    return Note(title=title, content=truncated, tags=tags)


def parse_markdown_notes(data: bytes) -> list[Note]:
    """Parse a single .md file or a ZIP of .md files."""
    notes: list[Note] = []

    # Try as ZIP first
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        md_files = [
            n for n in zf.namelist()
            if n.lower().endswith(".md")
            and not n.startswith("__MACOSX")
        ]
        if not md_files:
            raise AppError(
                "ZIP contains no .md files",
                code="no_markdown",
            )
        for name in md_files[:MAX_NOTES]:
            with zf.open(name) as fh:
                text = fh.read().decode(
                    "utf-8", errors="replace"
                )
            basename = name.rsplit("/", 1)[-1]
            notes.append(_parse_single_md(text, basename))
        return notes
    except zipfile.BadZipFile:
        pass

    # Treat as single markdown file
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as exc:
        raise AppError(
            "Cannot decode markdown file",
            code="bad_encoding",
        ) from exc

    if not text.strip():
        raise AppError("Empty markdown file", code="empty_file")

    notes.append(_parse_single_md(text, "note.md"))
    return notes
