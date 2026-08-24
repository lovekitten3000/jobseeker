"""Deterministic staleness scoping for the fetch layer.

A posting that hasn't been updated in over `max_age_days` is skipped before
it ever reaches triage — a board that never prunes its listings shouldn't
cost model calls on roles that were filled months ago. Like the location
filter, this is bookkeeping, not judgment: a posting with no parseable
`updated_at` is kept — missing data goes to triage, which can judge it; a
filter cannot.

Adapters normalize `updated_at` inconsistently: greenhouse/ashby/
smartrecruiters emit ISO 8601 strings, workable emits a bare date, lever
emits epoch milliseconds as a string. All are handled here.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def parse_updated_at(value: str) -> datetime | None:
    """Best-effort parse of an adapter's `updated_at` into an aware UTC time.

    Returns None when the value is empty or unrecognizable — callers must
    treat that as "unknown, keep", never as "stale".
    """
    v = (value or "").strip()
    if not v:
        return None
    # Epoch seconds (10 digits) or milliseconds (13 digits), as lever emits.
    if re.fullmatch(r"\d{10}", v):
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    if re.fullmatch(r"\d{13}", v):
        return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_fresh(updated_at: str, max_age_days: int, now: datetime | None = None) -> bool:
    """True when the posting was updated within `max_age_days`, or when its
    age is unknowable. `max_age_days <= 0` disables the filter entirely.
    """
    if max_age_days <= 0:
        return True
    parsed = parse_updated_at(updated_at)
    if parsed is None:
        return True
    if now is None:
        now = datetime.now(tz=timezone.utc)
    return now - parsed <= timedelta(days=max_age_days)
