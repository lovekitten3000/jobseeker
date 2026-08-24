"""Deterministic location scoping for the fetch layer.

`profile/targets.yaml` may set `location_filter`, a list of case-insensitive
regexes. A posting is kept when any pattern matches its location string.
This is bookkeeping, not judgment: it scopes which postings enter the queue
at all (a big employer's board lists every office worldwide), it never ranks
them. A posting with no location string is kept — missing data goes to
triage, which can judge it; a filter cannot.
"""
from __future__ import annotations

import re


def location_matches(location: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    if not location.strip():
        return True
    return any(re.search(p, location, re.IGNORECASE) for p in patterns)
