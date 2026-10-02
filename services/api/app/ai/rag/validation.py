"""Claim validation (SRD §18, §49): "No evidence, no factual claim."

Splits generated text into atomic claims and checks each against the retrieved
evidence. A claim is allowed when its specific content is supported, downgraded
when it overclaims leadership that evidence does not back ("Led" -> "Worked
on"), or rejected when its specifics (especially numbers) are unsupported.

The check is deterministic so professional outputs are gated reliably and
reproducibly, independent of any LLM's mood.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was", "were",
    "are", "our", "a", "an", "of", "to", "in", "on", "at", "by", "as", "is",
    "it", "be", "or", "using", "used", "built", "created", "developed", "worked",
}
_LEADERSHIP = {"led", "managed", "directed", "founded", "headed", "spearheaded", "oversaw"}
_SOFTENED = "Worked on"


class ClaimStatus(StrEnum):
    allow = "allow"
    downgrade = "downgrade"
    reject = "reject"


@dataclass
class ClaimVerdict:
    claim: str
    status: ClaimStatus
    reason: str
    suggestion: str | None = None


def split_claims(text: str) -> list[str]:
    # Sentence-ish split on ., ;, newline and bullet markers.
    raw = re.split(r"(?:[.;\n]|^\s*[-*•]\s*)+", text)
    return [c.strip() for c in raw if len(c.strip()) > 8]


def _content_tokens(s: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]*", s.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _numbers(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def validate_claim(claim: str, evidence_text: str, *, threshold: float = 0.5) -> ClaimVerdict:
    ev_lower = evidence_text.lower()
    ev_tokens = _content_tokens(evidence_text)
    ev_numbers = _numbers(evidence_text)

    claim_tokens = _content_tokens(claim)
    claim_numbers = _numbers(claim)

    # Numbers in a claim must be backed (e.g. "team of 20", "3 years").
    unbacked_numbers = claim_numbers - ev_numbers
    if unbacked_numbers:
        return ClaimVerdict(
            claim, ClaimStatus.reject,
            f"Unsupported figure(s): {', '.join(sorted(unbacked_numbers))}",
        )

    # Leadership verbs require evidence of leadership.
    claim_words = set(re.findall(r"[a-z]+", claim.lower()))
    leadership_in_claim = claim_words & _LEADERSHIP
    if leadership_in_claim and not (set(re.findall(r"[a-z]+", ev_lower)) & _LEADERSHIP):
        verb = next(iter(leadership_in_claim))
        softened = re.sub(rf"\b{verb}\b", _SOFTENED.lower(), claim, flags=re.IGNORECASE)
        softened = softened[0].upper() + softened[1:] if softened else softened
        return ClaimVerdict(
            claim, ClaimStatus.downgrade,
            f"No evidence of leadership ('{verb}')", suggestion=softened,
        )

    # Content overlap with evidence.
    if not claim_tokens:
        return ClaimVerdict(claim, ClaimStatus.allow, "No specific content to verify")
    overlap = len(claim_tokens & ev_tokens) / len(claim_tokens)
    if overlap >= threshold:
        return ClaimVerdict(claim, ClaimStatus.allow, f"Supported (overlap {overlap:.0%})")
    return ClaimVerdict(
        claim, ClaimStatus.reject, f"Insufficient support (overlap {overlap:.0%})"
    )


def validate_text(text: str, evidence_text: str) -> list[ClaimVerdict]:
    return [validate_claim(c, evidence_text) for c in split_claims(text)]


def apply_verdicts(verdicts: list[ClaimVerdict]) -> str:
    """Rebuild text keeping allowed claims and softened downgrades, dropping rejects."""
    kept: list[str] = []
    for v in verdicts:
        if v.status == ClaimStatus.allow:
            kept.append(v.claim)
        elif v.status == ClaimStatus.downgrade and v.suggestion:
            kept.append(v.suggestion)
    return ". ".join(kept) + ("." if kept else "")
