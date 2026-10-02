"""Writing-style analysis (SRD §8.6).

Computes simple, deterministic metrics from the user's own writing so generated
content can be adapted to their voice — without ever falsely attributing text to
them. Stored per persona in the writing_styles table.
"""

from __future__ import annotations

import re
import statistics
from typing import Any

_CONTRACTIONS = re.compile(r"\b\w+'\w+\b")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE = re.compile(r"[.!?]+")


def analyze_style(texts: list[str]) -> dict[str, Any]:
    text = "\n".join(t for t in texts if t).strip()
    if len(text) < 200:
        return {}

    sentences = [s.strip() for s in _SENTENCE.split(text) if len(s.strip()) > 1]
    words = _WORD.findall(text)
    if not sentences or not words:
        return {}

    lower_words = [w.lower() for w in words]
    sentence_lengths = [len(_WORD.findall(s)) for s in sentences] or [0]
    word_lengths = [len(w) for w in words]

    contractions = len(_CONTRACTIONS.findall(text))
    exclamations = text.count("!")
    questions = text.count("?")
    unique_ratio = len(set(lower_words)) / len(lower_words)
    long_words = sum(1 for w in words if len(w) >= 7) / len(words)

    # Heuristic formality: more contractions/exclamations -> less formal.
    informality = (contractions + exclamations) / max(len(sentences), 1)
    formality = max(0.0, min(1.0, 1.0 - informality))

    return {
        "sample_sentences": len(sentences),
        "avg_sentence_length": round(statistics.mean(sentence_lengths), 1),
        "avg_word_length": round(statistics.mean(word_lengths), 2),
        "vocabulary_richness": round(unique_ratio, 3),
        "long_word_ratio": round(long_words, 3),
        "formality": round(formality, 2),
        "uses_contractions": contractions > 0,
        "exclamation_rate": round(exclamations / max(len(sentences), 1), 3),
        "question_rate": round(questions / max(len(sentences), 1), 3),
    }


def style_descriptor(metrics: dict[str, Any]) -> str:
    """A short natural-language hint for generation prompts."""
    if not metrics:
        return ""
    parts: list[str] = []
    asl = metrics.get("avg_sentence_length", 0)
    if asl:
        parts.append(
            "short, punchy sentences" if asl < 14
            else "longer, detailed sentences" if asl > 22
            else "medium-length sentences"
        )
    formality = metrics.get("formality", 0.5)
    parts.append("a formal tone" if formality > 0.7 else "a casual tone" if formality < 0.4
                 else "a balanced tone")
    if metrics.get("uses_contractions"):
        parts.append("contractions are fine")
    if metrics.get("long_word_ratio", 0) > 0.25:
        parts.append("a technical vocabulary")
    return "Match the author's voice: " + ", ".join(parts) + "."
