"""Teamtailor adapter. PRD §4.1.

Teamtailor career sites publish a public JSON Feed at `/jobs.json` on the
board's own host, so a target's `slug` is that host:

    {host}           e.g.  careers.<company>.com

Each feed item carries a JSON-LD `_jobposting` (schema.org JobPosting) with the
location(s), description, and posted date — no per-posting detail call needed.
A single GET; no pagination (the feed is the whole board).
"""
from __future__ import annotations

import re

from locations import location_matches
from schema import Posting
from sources._http import get_json


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _locations(jobposting: dict) -> str:
    """Join a JobPosting's one-or-many jobLocation places into a location string.

    A role often lists several offices; keeping them all lets fetch.py's
    location filter see any one of them, not just the first.
    """
    locs = jobposting.get("jobLocation") or []
    if isinstance(locs, dict):
        locs = [locs]
    parts = []
    for loc in locs:
        addr = (loc or {}).get("address", {}) or {}
        one = ", ".join(
            x
            for x in (
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
            )
            if x
        )
        if one:
            parts.append(one)
    return "; ".join(parts)


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    host = slug.strip().strip("/")
    data = get_json(f"https://{host}/jobs.json")
    items = data.get("items", []) if isinstance(data, dict) else []
    out: list[Posting] = []
    for item in items:
        jp = item.get("_jobposting", {}) or {}
        location = _locations(jp)
        if not location_matches(location, location_filter):
            continue
        org = (jp.get("hiringOrganization") or {}).get("name", "")
        description = _strip_html(jp.get("description", "") or item.get("content_html", ""))
        out.append(
            Posting(
                source="teamtailor",
                slug=slug,
                company=org or host.split(".")[0],
                title=item.get("title", "") or jp.get("title", ""),
                location=location,
                url=item.get("url", "") or "",
                department="",
                updated_at=item.get("date_published", "") or jp.get("datePosted", "") or "",
                description=description,
            )
        )
    return out
