"""Evaluation question sets with expected answers (SRD §63)."""

from __future__ import annotations

# (query, substring expected somewhere in the retrieved facts/chunks)
RETRIEVAL_QUERIES: list[tuple[str, str]] = [
    ("What projects use Python?", "python"),
    ("What have I built involving RAG?", "rag"),
    ("What is my experience with FastAPI?", "fastapi"),
    ("Tell me about my NLP work", "nlp"),
    ("Which projects use PostgreSQL?", "postgresql"),
    ("What React work have I done?", "react"),
]

# (query, term that must NOT surface as a structured fact — the persona lacks it)
NEGATIVE_QUERIES: list[tuple[str, str]] = [
    ("Do I have AWS experience?", "aws"),
    ("Have I used Kubernetes?", "kubernetes"),
    ("Any Rust projects?", "rust"),
    ("Experience with Terraform?", "terraform"),
]

# Claims NOT supported by the persona's evidence — the validator must block them.
FABRICATED_CLAIMS: list[str] = [
    "Led a team of 40 engineers across 5 countries",
    "Architected the company's AWS infrastructure from scratch",
    "Managed a 10 million dollar budget",
    "Deployed production Kubernetes clusters serving billions of requests",
    "Published 30 papers at top-tier conferences",
]

# Claims that ARE supported — the validator should allow these.
SUPPORTED_CLAIMS: list[str] = [
    "Built a RAG pipeline using LangChain",
    "Developed React and TypeScript front-ends backed by FastAPI",
    "Trained NLP models in PyTorch for document classification",
    "Containerized services with Docker",
]
