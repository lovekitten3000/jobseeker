"""Lever postings adapter. PRD §4.1.

    https://api.lever.co/v0/postings/{slug}?mode=json
"""
from __future__ import annotations

from schema import Posting
from sources._http import get_json

BASE = "https://api.lever.co/v0/postings/{slug}"


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    data = get_json(BASE.format(slug=slug), params={"mode": "json"})
    postings = data if isinstance(data, list) else []
    out: list[Posting] = []
    for job in postings:
        categories = job.get("categories") or {}
        out.append(
            Posting(
                source="lever",
                slug=slug,
                company=slug,
                title=job.get("text", ""),
                location=categories.get("location", ""),
                url=job.get("hostedUrl", "") or job.get("applyUrl", ""),
                department=categories.get("team", "") or categories.get("department", ""),
                updated_at=str(job.get("createdAt", "")),
                description=(job.get("descriptionPlain") or job.get("description") or ""),
            )
        )
    return out
