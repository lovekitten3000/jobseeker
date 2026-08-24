"""Workable widget adapter. PRD §4.1.

    https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true

The widget payload carries location as flat top-level `city`/`state`/`country`
fields (NOT a nested `location` object), plus a `locations` array for
multi-location roles and a `telecommuting` flag for remote ones. Reading the
wrong shape leaves every posting with an empty location string, which the
location filter treats as "keep and let triage decide" — silently pulling
in-office US/global roles as if they were in-scope. So location parsing here is
load-bearing, not cosmetic.

Note: an account whose feed is empty (widget returns the account `name` but
`jobs: []`) has left Workable or unpublished its board — there is nothing to
fetch, and that is not an adapter fault.
"""
from __future__ import annotations

from schema import Posting
from sources._http import get_json

BASE = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


def _location(job: dict) -> str:
    """Best-effort single location string from the widget's several shapes.

    Order: flat city/state/country -> a nested `location` dict (defensive, some
    payloads differ) -> the first entry of the `locations` array -> remote.
    """
    city = job.get("city") or ""
    state = job.get("state") or ""
    country = job.get("country") or ""

    # Defensive: some payloads nest the fields under `location` instead.
    loc = job.get("location")
    if isinstance(loc, dict):
        city = city or loc.get("city", "")
        state = state or loc.get("region", "") or loc.get("state", "")
        country = country or loc.get("country", "")

    parts = [p for p in (city, state, country) if p]
    if parts:
        return ", ".join(parts)

    # Multi-location roles: fall back to the first entry of `locations`.
    locs = job.get("locations")
    if isinstance(locs, list) and locs:
        first = locs[0]
        if isinstance(first, dict):
            parts = [
                first.get(k, "")
                for k in ("city", "region", "country")
                if first.get(k)
            ]
            if parts:
                return ", ".join(parts)
        elif isinstance(first, str) and first:
            return first

    if job.get("telecommuting") or (isinstance(loc, dict) and loc.get("workplace") == "remote"):
        return "Remote"
    return ""


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    data = get_json(BASE.format(slug=slug), params={"details": "true"})
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    company = data.get("name", slug) if isinstance(data, dict) else slug
    out: list[Posting] = []
    for job in jobs:
        out.append(
            Posting(
                source="workable",
                slug=slug,
                company=company,
                title=job.get("title", ""),
                location=_location(job),
                url=job.get("url", "") or job.get("shortlink", "") or job.get("application_url", ""),
                department=job.get("department", ""),
                updated_at=job.get("published_on", "") or job.get("created_at", ""),
                description=job.get("description", ""),
            )
        )
    return out
