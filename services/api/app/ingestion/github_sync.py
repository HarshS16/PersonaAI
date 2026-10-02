"""GitHub source sync: fetch repos and map them into the persona.

Repositories become projects, languages become skills, and READMEs are stored
as embedded chunks for semantic search. Evidence is weighted as a GitHub source
(0.5), below a resume, and merged through the same conflict-aware engine.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.ai.embeddings import get_embedder
from app.ai.extraction import ExtractedProject, ExtractedSkill, ResumeExtraction
from app.connectors.base import GitHubData
from app.connectors.github import get_github_client
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.security import decrypt_secret
from app.domain.merge import merge_extraction
from app.domain.persona import EVIDENCE_WEIGHTS, compute_completeness, snapshot_persona
from app.ingestion.chunk import chunk_text
from app.ingestion.pipeline import SessionFactory, _set_progress
from app.models.ingestion import Chunk, Document, Job, Source
from app.models.persona import Persona

log = get_logger("github_sync")
_GH_W = EVIDENCE_WEIGHTS["github_language"]


def _build_extraction(data: GitHubData) -> ResumeExtraction:
    projects: list[ExtractedProject] = []
    skills: dict[str, ExtractedSkill] = {}

    for repo in data.repos:
        techs = repo.languages or ([repo.primary_language] if repo.primary_language else [])
        # Forks are noisy as "projects"; still mine their languages for skills.
        if not repo.is_fork:
            desc = repo.description or (
                repo.readme.splitlines()[0].lstrip("# ").strip() if repo.readme else repo.name
            )
            quote = repo.description or f"GitHub repository {repo.full_name}"
            projects.append(
                ExtractedProject(
                    name=repo.name, description=desc, technologies=techs, quote=quote
                )
            )
        for lang in techs:
            key = lang.lower()
            if key not in skills:
                skills[key] = ExtractedSkill(
                    name=lang, category="Language", quote=f"Used in {repo.name} on GitHub"
                )

    return ResumeExtraction(projects=projects, skills=list(skills.values()))


async def sync_github_job(
    job_id: uuid.UUID, session_factory: SessionFactory | None = None
) -> dict[str, Any]:
    sf: SessionFactory = session_factory or SessionLocal
    async with sf() as s:
        job = await s.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.status = "running"
        job.attempts += 1
        await s.commit()

    try:
        summary = await _run(sf, job_id)
    except Exception as exc:  # noqa: BLE001
        log.error("github_sync_failed", job_id=str(job_id), error=str(exc))
        async with sf() as s:
            job = await s.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)[:1000]
                if job.source_id:
                    src = await s.get(Source, job.source_id)
                    if src:
                        src.status = "error"
                        src.error = str(exc)[:1000]
                await s.commit()
        raise

    async with sf() as s:
        job = await s.get(Job, job_id)
        if job:
            job.status = "succeeded"
            job.progress = 1.0
            job.step = "done"
            job.result = summary
            await s.commit()
    return summary


async def _get_token(s: Any, persona: Persona) -> str | None:
    from app.models.user import OAuthAccount, OAuthProvider

    result = await s.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == persona.user_id,
            OAuthAccount.provider == OAuthProvider.github,
        )
    )
    account = result.scalar_one_or_none()
    if account and account.access_token_enc:
        try:
            return decrypt_secret(account.access_token_enc)
        except Exception:  # pragma: no cover
            return None
    return None


async def _run(sf: SessionFactory, job_id: uuid.UUID) -> dict[str, Any]:
    async with sf() as s:
        job = await s.get(Job, job_id)
        assert job is not None
        source = await s.get(Source, job.source_id) if job.source_id else None
        assert source is not None
        persona = await s.get(Persona, job.persona_id)
        assert persona is not None

        username = source.stats.get("username") if source.stats else None
        token = await _get_token(s, persona)

        await _set_progress(sf, job_id, step="fetching", progress=0.2)
        client = get_github_client()
        data = await client.fetch(token=token, username=username)

        # Store READMEs as embedded, searchable chunks.
        await _set_progress(sf, job_id, step="embedding", progress=0.5)
        embedder = get_embedder()
        chunks_for_merge: list[tuple[uuid.UUID, str]] = []
        for repo in data.repos:
            if not repo.readme:
                continue
            doc = Document(
                source_id=source.id,
                persona_id=persona.id,
                title=repo.full_name,
                mime="text/markdown",
                content=repo.readme,
                content_hash=hashlib.sha256(
                    f"{repo.full_name}:{repo.readme}".encode()
                ).hexdigest(),
                doc_metadata={"repo": repo.full_name, "url": repo.html_url},
            )
            s.add(doc)
            await s.flush()
            text_chunks = chunk_text(repo.readme)
            vectors = await embedder.embed([tc.text for tc in text_chunks])
            for tc, vec in zip(text_chunks, vectors, strict=True):
                ch = Chunk(
                    document_id=doc.id,
                    persona_id=persona.id,
                    ordinal=tc.ordinal,
                    text=tc.text,
                    embedding=vec,
                    chunk_metadata={"repo": repo.full_name, "section": tc.section},
                )
                s.add(ch)
                await s.flush()
                chunks_for_merge.append((ch.id, ch.text))

        # Snapshot before mutating the persona (recoverable).
        await snapshot_persona(s, persona, reason=f"Before GitHub sync ({data.username})")

        await _set_progress(sf, job_id, step="merging", progress=0.8)
        extraction = _build_extraction(data)
        summary = await merge_extraction(
            s,
            persona,
            extraction,
            source_id=source.id,
            chunks=chunks_for_merge,
            source_label="github",
            evidence_weight=_GH_W,
        )

        await compute_completeness(s, persona)
        source.status = "synced"
        source.last_synced = datetime.now(UTC)
        source.provider = "github"
        stats = dict(source.stats or {})
        stats.update(
            {
                "username": data.username,
                "repos": len(data.repos),
                "created": summary.to_dict()["created"],
            }
        )
        source.stats = stats
        await s.commit()
        return summary.to_dict()
