"""Ashby job-board adapter. PRD §4.1.

    https://api.ashbyhq.com/posting-api/job-board/{slug}
"""
from __future__ import annotations

from schema import Posting
from sources._http import get_json

BASE = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    data = get_json(BASE.format(slug=slug), params={"includeCompensation": "true"})
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out: list[Posting] = []
    for job in jobs:
        out.append(
            Posting(
                source="ashby",
                slug=slug,
                company=slug,
                title=job.get("title", ""),
                location=job.get("location", ""),
                url=job.get("jobUrl", "") or job.get("applyUrl", ""),
                department=job.get("department", "") or job.get("team", ""),
                updated_at=job.get("publishedAt", "") or job.get("updatedAt", ""),
                description=job.get("descriptionPlain", "") or job.get("description", ""),
            )
        )
    return out
