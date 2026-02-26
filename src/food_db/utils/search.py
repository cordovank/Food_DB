from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


_WORD_RE = re.compile(r"[a-z0-9]+", re.I)


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[\s\-_]+", " ", s).strip()
    return s


def _tokens(s: str) -> list[str]:
    return _WORD_RE.findall(_norm(s))


def fuzzy_score(query: str, candidate: str) -> float:
    """
    Returns a score in [0, 1].
    Boosts exact substring/token overlap, then falls back to SequenceMatcher ratio.
    """
    qn = _norm(query)
    cn = _norm(candidate)
    if not qn or not cn:
        return 0.0

    # Strong boost for direct substring match
    if qn in cn:
        return 1.0

    qt = set(_tokens(qn))
    ct = set(_tokens(cn))
    if not qt or not ct:
        return SequenceMatcher(None, qn, cn).ratio()

    overlap = len(qt & ct) / max(1, len(qt))

    # Sequence similarity for misspellings / OCR noise
    ratio = SequenceMatcher(None, qn, cn).ratio()

    # Weighted combo: overlap dominates for multi-word queries
    return max(0.0, min(1.0, 0.65 * overlap + 0.35 * ratio))


@dataclass(frozen=True)
class Ranked:
    id: int
    score: float