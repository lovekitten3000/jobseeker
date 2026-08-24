"""Greenhouse board adapter. PRD §4.1.

    https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
"""
from __future__ import annotations

import re

from schema import Posting
from sources._http import get_json

BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    data = get_json(BASE.format(slug=slug), params={"content": "true"})
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out: list[Posting] = []
    for job in jobs:
        offices = job.get("offices") or []
        location = (job.get("location") or {}).get("name", "")
        if not location and offices:
            location = offices[0].get("name", "")
        out.append(
            Posting(
                source="greenhouse",
                slug=slug,
                company=slug,
                title=job.get("title", ""),
                location=location,
                url=job.get("absolute_url", ""),
                department=(job.get("departments") or [{}])[0].get("name", ""),
                updated_at=job.get("updated_at", ""),
                description=_strip_html(job.get("content", "")),
            )
        )
    return out
