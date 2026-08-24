"""Shared data models for Jobseeker.

Deliberately small. These types are the contract between the fetch layer,
the seen-state index, and the tracker. Nothing here talks to a model, and
nothing here reads personal data — that all lives in the private instance.
"""
from __future__ import annotations

import hashlib
import re

from pydantic import BaseModel, Field, field_validator


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace, strip common seniority punctuation.

    Two postings whose titles differ only by casing or spacing are the same
    job for dedupe purposes. We intentionally do NOT strip seniority words
    (Senior, Staff) — those are real distinctions.
    """
    t = title.strip().lower()
    t = re.sub(r"[‐-―\-/]+", " ", t)  # dashes and slashes -> space
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


class Posting(BaseModel):
    """A single job posting, normalized across ATS providers.

    `source` is the adapter name (greenhouse, lever, ...). `slug` is the
    company board slug on that ATS. `url` is where a human would apply.
    """

    source: str
    slug: str
    company: str
    title: str
    location: str = ""
    url: str = ""
    department: str = ""
    updated_at: str = ""
    description: str = ""

    @field_validator(
        "source", "slug", "company", "title", "location", "url",
        "department", "updated_at", "description", mode="before",
    )
    @classmethod
    def _none_to_empty(cls, v: object) -> object:
        """Coerce a null JSON value to "".

        ATS payloads frequently carry an explicit `null` for a field an adapter
        reads (`location: null`, a missing `name`). `dict.get(k, "")` returns
        that None, and a None reaching a `str` field would raise and sink the
        WHOLE board (fetch.py counts it as one adapter failure — PRD §8.1).
        Coercing here, at the one place every adapter funnels through, keeps a
        single null field from costing a company's entire posting list.
        """
        return "" if v is None else v

    def fingerprint(self) -> str:
        """Stable identity: sha256(company + normalized_title + location).

        This is the dedupe key and the seen-state key. It must be derivable
        from a Posting alone, with no network access, so a re-fetch on a
        fresh VM produces byte-identical fingerprints. See PRD §6.
        """
        basis = "\x1f".join(
            [
                self.company.strip().lower(),
                normalize_title(self.title),
                self.location.strip().lower(),
            ]
        )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def slugify(self) -> str:
        """Directory-safe slug for queue/ready/<slug>/, e.g. acme-staff-eng."""
        base = f"{self.company}-{self.title}"
        base = base.lower()
        base = re.sub(r"[^a-z0-9]+", "-", base)
        return base.strip("-")[:60]


class SeenEntry(BaseModel):
    """One row in a state/seen/<date>.jsonl shard.

    Written only when a posting reaches a terminal disposition — killed by
    triage, or landed in queue/shortlist/. Never at fetch time. See PRD §6,
    §15. A shortlisted role later discarded at /tailor needs no new record.
    """

    fingerprint: str
    company: str
    title: str
    disposition: str = Field(description="killed | shortlisted (legacy: queued)")
    date: str = ""
