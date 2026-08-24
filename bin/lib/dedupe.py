"""Dedupe postings against the seen-index and against each other. PRD §8.1."""
from __future__ import annotations

from typing import Iterable

from schema import Posting


def dedupe(postings: Iterable[Posting], seen: set[str]) -> list[Posting]:
    """Drop postings whose fingerprint is already in `seen` or repeats within
    this batch. Order-preserving; first occurrence wins.
    """
    out: list[Posting] = []
    batch: set[str] = set()
    for p in postings:
        fp = p.fingerprint()
        if fp in seen or fp in batch:
            continue
        batch.add(fp)
        out.append(p)
    return out
