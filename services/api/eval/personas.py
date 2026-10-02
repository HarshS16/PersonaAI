"""Synthetic persona fixtures for evaluation (SRD §63).

Builds a deterministic persona with skills, experience, projects, publications
and a couple of embedded documents so retrieval, grounding and hallucination
metrics can be measured reproducibly.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedder
from app.domain.persona import add_manual_evidence, get_or_create_persona
from app.ingestion.chunk import chunk_text
from app.models.enums import EntityType, EvidenceState, Visibility
from app.models.evidence import Evidence
from app.models.facts import Experience, Project, Publication, Skill
from app.models.ingestion import Chunk, Document, Source
from app.models.persona import Persona
from app.models.user import User

# Facts present in the synthetic persona. Anything NOT here (AWS, Kubernetes,
# Rust…) is a valid "negative" for hallucination testing.
SKILLS = ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "LangChain",
          "RAG", "PyTorch", "NLP", "TypeScript"]
ABSENT_SKILLS = ["AWS", "Kubernetes", "Rust", "Kotlin", "Terraform"]

PROJECTS = [
    ("RAG Search", "A retrieval-augmented search engine over documents",
     ["Python", "LangChain", "RAG", "PostgreSQL"]),
    ("Resume Analyzer", "Parses resumes and scores them against job descriptions",
     ["Python", "FastAPI", "PyTorch"]),
    ("Portfolio Site", "Personal portfolio built as a static site",
     ["React", "TypeScript"]),
    ("NLP Toolkit", "A library of text-processing utilities",
     ["Python", "NLP"]),
    ("Container Platform", "Internal service deployment tooling",
     ["Docker", "PostgreSQL"]),
]

EXPERIENCES = [
    ("Senior Software Engineer", "WebBee Global",
     "Built a RAG pipeline and migrated services to FastAPI and PostgreSQL."),
    ("Machine Learning Engineer", "DataWorks",
     "Trained NLP models in PyTorch for document classification."),
    ("Full-Stack Developer", "Startly",
     "Developed React and TypeScript front-ends backed by FastAPI."),
    ("Backend Intern", "CloudNine",
     "Containerized services with Docker and wrote PostgreSQL schemas."),
    ("Open Source Contributor", "LangChain",
     "Contributed retrieval components to an open-source RAG framework."),
]

PUBLICATIONS = [
    ("Efficient Retrieval for RAG Systems", "NeurIPS Workshop", 2024),
    ("Evaluating Grounded Generation", "ACL", 2025),
    ("Document Chunking Strategies", "EMNLP", 2023),
]

DOCUMENTS = [
    (
        "resume.txt",
        "Harsh Srivastava — AI Engineer. Experience: Senior Software Engineer at "
        "WebBee Global, built a RAG pipeline using LangChain and FAISS. Skills: "
        "Python, FastAPI, React, PostgreSQL, Docker, LangChain, PyTorch, NLP.",
    ),
    (
        "rag-search-readme.md",
        "# RAG Search\nA retrieval-augmented generation search engine built with "
        "Python, LangChain and PostgreSQL pgvector. Supports hybrid semantic and "
        "keyword retrieval with reciprocal rank fusion.",
    ),
]


async def build_synthetic_persona(
    session: AsyncSession, email: str = "eval@example.com"
) -> Persona:
    user = User(email=email, name="Eval Persona")
    session.add(user)
    await session.flush()

    persona = await get_or_create_persona(session, user.id)
    persona.full_name = "Eval Persona"
    persona.headline = "AI Engineer"

    for name in SKILLS:
        skill = Skill(
            persona_id=persona.id, name=name, canonical_name=name.lower(),
            category="skill", state=EvidenceState.verified, confidence=0.9, evidence_count=1,
            visibility=Visibility.public,
        )
        session.add(skill)
        await session.flush()
        await _ev(session, persona.id, EntityType.skill, skill.id, f"Used {name} in production.")

    for role, company, desc in EXPERIENCES:
        exp = Experience(
            persona_id=persona.id, role=role, company=company, description=desc,
            state=EvidenceState.verified, confidence=0.8,
        )
        session.add(exp)
        await session.flush()
        await _ev(session, persona.id, EntityType.experience, exp.id, desc)

    for name, desc, techs in PROJECTS:
        proj = Project(
            persona_id=persona.id, name=name, description=desc, technologies=techs,
            state=EvidenceState.verified, confidence=0.85,
        )
        session.add(proj)
        await session.flush()
        await _ev(session, persona.id, EntityType.project, proj.id, desc)

    for title, venue, year in PUBLICATIONS:
        pub = Publication(
            persona_id=persona.id, title=title, venue=venue, year=year,
            state=EvidenceState.verified, confidence=0.8,
        )
        session.add(pub)
        await session.flush()
        await _ev(session, persona.id, EntityType.publication, pub.id, f"{title} ({venue}, {year})")

    # Documents + embedded chunks for semantic/keyword retrieval.
    source = Source(persona_id=persona.id, type="resume", provider="eval", title="eval docs",
                    status="synced")
    session.add(source)
    await session.flush()
    embedder = get_embedder()
    for title, content in DOCUMENTS:
        doc = Document(source_id=source.id, persona_id=persona.id, title=title,
                       content=content, content_hash=uuid.uuid4().hex, doc_metadata={})
        session.add(doc)
        await session.flush()
        chunks = chunk_text(content)
        vectors = await embedder.embed([c.text for c in chunks])
        for c, vec in zip(chunks, vectors, strict=True):
            session.add(Chunk(document_id=doc.id, persona_id=persona.id, ordinal=c.ordinal,
                              text=c.text, embedding=vec, chunk_metadata={}))

    await session.flush()
    return persona


async def _ev(
    session: AsyncSession, persona_id: uuid.UUID, et: EntityType, eid: uuid.UUID, quote: str
) -> None:
    session.add(Evidence(
        persona_id=persona_id, entity_type=et, entity_id=eid, content=quote,
        locator={"source": "eval"}, state=EvidenceState.verified, confidence=0.6,
    ))
    _ = add_manual_evidence  # (kept importable for callers that want user-confirmed evidence)
