"""Section-aware chunking.

Resumes and similar documents are organized by headings. We keep paragraphs
together under their nearest heading and cap chunk size by character count,
which is good enough for retrieval without a tokenizer dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(
    r"^(?:#+\s*)?("
    r"experience|work experience|employment|education|skills|technical skills|"
    r"projects|publications|research|achievements|awards|certifications|summary|"
    r"about|profile|contact|interests)\b",
    re.IGNORECASE,
)


@dataclass
class TextChunk:
    ordinal: int
    text: str
    section: str | None


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 100) -> list[TextChunk]:
    lines = text.splitlines()
    chunks: list[TextChunk] = []
    current_section: str | None = None
    buffer: list[str] = []
    ordinal = 0

    def flush() -> None:
        nonlocal buffer, ordinal
        body = "\n".join(buffer).strip()
        if body:
            chunks.append(TextChunk(ordinal=ordinal, text=body, section=current_section))
            ordinal += 1
        buffer = []

    for line in lines:
        heading = _HEADING_RE.match(line.strip())
        if heading:
            flush()
            current_section = heading.group(1).lower()
            buffer.append(line)
            continue

        buffer.append(line)
        if sum(len(b) + 1 for b in buffer) >= max_chars:
            flush()
            # Carry a little overlap for context continuity.
            if overlap and chunks:
                tail = chunks[-1].text[-overlap:]
                buffer = [tail]

    flush()

    # Guarantee at least one chunk for non-empty input.
    if not chunks and text.strip():
        chunks.append(TextChunk(ordinal=0, text=text.strip()[:max_chars], section=None))
    return chunks
