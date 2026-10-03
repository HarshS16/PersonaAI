"""Research imports: arXiv, Semantic Scholar, and ORCID (SRD §57).

All three expose free public APIs. We parse the author's publications and map
them into the persona's publication + skill models.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.ai.extraction import ResumeExtraction
from app.core.errors import AppError
from app.core.logging import get_logger

log = get_logger("research")


@dataclass
class PaperResult:
    title: str
    venue: str | None = None
    year: int | None = None
    url: str | None = None
    abstract: str | None = None


@dataclass
class ResearchData:
    papers: list[PaperResult] = field(default_factory=list)
    name: str | None = None


# ---------------------------------------------------------------------------
# Semantic Scholar (free, no key needed for small volume)
# ---------------------------------------------------------------------------

_S2_BASE = "https://api.semanticscholar.org/graph/v1"


async def fetch_semantic_scholar(author_query: str) -> ResearchData:
    """Search by author name and return their papers."""
    async with httpx.AsyncClient(timeout=15) as client:
        search = await client.get(
            f"{_S2_BASE}/author/search",
            params={"query": author_query, "limit": 1},
        )
        if search.status_code != 200:
            raise AppError("Semantic Scholar search failed", code="s2_error")
        authors = search.json().get("data", [])
        if not authors:
            raise AppError("No author found on Semantic Scholar", code="s2_not_found")

        author_id = authors[0]["authorId"]
        name = authors[0].get("name")

        papers_resp = await client.get(
            f"{_S2_BASE}/author/{author_id}/papers",
            params={"fields": "title,venue,year,url,abstract", "limit": 50},
        )
        if papers_resp.status_code != 200:
            raise AppError("Could not fetch papers", code="s2_error")

        data = ResearchData(name=name)
        for p in papers_resp.json().get("data", []):
            data.papers.append(PaperResult(
                title=p.get("title", ""),
                venue=p.get("venue") or None,
                year=p.get("year"),
                url=p.get("url"),
                abstract=p.get("abstract"),
            ))
        return data


# ---------------------------------------------------------------------------
# arXiv (free, no auth)
# ---------------------------------------------------------------------------

_ARXIV_API = "http://export.arxiv.org/api/query"


async def fetch_arxiv(author_name: str, max_results: int = 30) -> ResearchData:
    """Search arXiv for papers by this author."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            _ARXIV_API,
            params={
                "search_query": f"au:{author_name}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
        )
        if resp.status_code != 200:
            raise AppError("arXiv query failed", code="arxiv_error")

    # arXiv returns Atom XML; parse with minimal approach.
    import xml.etree.ElementTree as ET

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    data = ResearchData(name=author_name)
    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        summary_el = entry.find("a:summary", ns)
        published_el = entry.find("a:published", ns)
        link_el = entry.find("a:id", ns)
        year = None
        if published_el is not None and published_el.text:
            year = int(published_el.text[:4])
        data.papers.append(PaperResult(
            title=(title_el.text or "").strip().replace("\n", " ") if title_el is not None else "",
            venue="arXiv",
            year=year,
            url=(link_el.text or "").strip() if link_el is not None else None,
            abstract=(summary_el.text or "").strip()[:500] if summary_el is not None else None,
        ))
    return data


# ---------------------------------------------------------------------------
# ORCID (free public API)
# ---------------------------------------------------------------------------

_ORCID_API = "https://pub.orcid.org/v3.0"


async def fetch_orcid(orcid_id: str) -> ResearchData:
    """Fetch works from an ORCID profile."""
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        works_resp = await client.get(f"{_ORCID_API}/{orcid_id}/works")
        if works_resp.status_code == 404:
            raise AppError("ORCID profile not found", code="orcid_not_found")
        if works_resp.status_code != 200:
            raise AppError("ORCID API error", code="orcid_error")

        person_resp = await client.get(f"{_ORCID_API}/{orcid_id}/person")
        name = None
        if person_resp.status_code == 200:
            pdata = person_resp.json().get("name", {})
            given = (pdata.get("given-names") or {}).get("value", "")
            family = (pdata.get("family-name") or {}).get("value", "")
            name = f"{given} {family}".strip() or None

    works = works_resp.json()
    data = ResearchData(name=name)
    for group in works.get("group", [])[:50]:
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        w = summaries[0]
        title_obj = w.get("title", {}).get("title", {})
        title = title_obj.get("value", "") if title_obj else ""
        journal = (w.get("journal-title") or {}).get("value")
        year = None
        pub_date = w.get("publication-date") or {}
        if pub_date.get("year"):
            year = int(pub_date["year"]["value"])

        # External URL
        url = None
        ext_ids = w.get("external-ids", {}).get("external-id", [])
        for eid in ext_ids:
            if eid.get("external-id-url"):
                url = eid["external-id-url"].get("value")
                break

        data.papers.append(PaperResult(
            title=title, venue=journal, year=year, url=url,
        ))
    return data


# ---------------------------------------------------------------------------
# Shared: convert research data → extraction for merge
# ---------------------------------------------------------------------------


def research_to_extraction(data: ResearchData) -> ResumeExtraction:
    """Map research papers to publications + inferred skills."""
    from app.ai.extraction import ExtractedPublication
    extraction = ResumeExtraction()
    if data.name:
        extraction.full_name = data.name
    for p in data.papers:
        extraction.publications.append(ExtractedPublication(
            title=p.title,
            venue=p.venue,
            year=p.year,
            url=p.url,
            quote=f"Published: {p.title}" + (f" in {p.venue}" if p.venue else ""),
        ))
    return extraction


class FakeResearchClient:
    """Deterministic fake for tests."""

    async def fetch(self, provider: str, query: str) -> ResearchData:
        return ResearchData(
            name="Dr. Test Author",
            papers=[
                PaperResult(
                    title="Attention Is All You Need",
                    venue="NeurIPS",
                    year=2017,
                    url="https://arxiv.org/abs/1706.03762",
                    abstract="We propose a new architecture based on attention mechanisms.",
                ),
                PaperResult(
                    title="BERT: Pre-training of Deep Bidirectional Transformers",
                    venue="NAACL",
                    year=2019,
                    url="https://arxiv.org/abs/1810.04805",
                ),
            ],
        )
