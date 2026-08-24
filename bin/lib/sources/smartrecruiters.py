"""SmartRecruiters postings adapter. PRD §4.1.

    https://api.smartrecruiters.com/v1/companies/{slug}/postings

The list endpoint pages at 100 and carries no ad text, so this adapter
paginates, then fetches each posting's detail for the description and the
candidate-facing URL. Internal calls sleep 1s apiece: fetch.py's ≤1
req/sec/host budget only covers the gaps between adapter invocations, so
requests made inside one invocation must pace themselves.
"""
from __future__ import annotations

import re
import time

from locations import location_matches
from schema import Posting
from sources._http import get_json

BASE = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE_SIZE = 100


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _list_postings(slug: str) -> list[dict]:
    postings: list[dict] = []
    offset = 0
    while True:
        data = get_json(
            BASE.format(slug=slug), params={"limit": PAGE_SIZE, "offset": offset}
        )
        if not isinstance(data, dict):
            break
        page = data.get("content", [])
        postings.extend(page)
        offset += len(page)
        if not page or offset >= data.get("totalFound", 0):
            break
        time.sleep(1.0)
    return postings


def _detail(slug: str, posting_id: str) -> tuple[str, str]:
    """Return (description, posting_url) from the per-posting endpoint.

    The list response includes neither. A failed detail call degrades to
    empty fields rather than killing the whole board.
    """
    try:
        detail = get_json(BASE.format(slug=slug) + f"/{posting_id}")
    except Exception:  # noqa: BLE001 — one dead posting must not kill the board
        return "", ""
    if not isinstance(detail, dict):
        return "", ""
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    description = " ".join(
        part
        for part in (
            _strip_html((sections.get(key) or {}).get("text", ""))
            for key in ("jobDescription", "qualifications", "additionalInformation")
        )
        if part
    )
    return description, detail.get("postingUrl", "")


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    out: list[Posting] = []
    for job in _list_postings(slug):
        loc = job.get("location") or {}
        city = loc.get("city", "")
        country = loc.get("country", "")
        location = ", ".join(x for x in (city, country) if x)
        if loc.get("remote"):
            location = (location + " (Remote)").strip()
        # The list response carries the location, so skip the expensive detail
        # call for postings the location filter would drop anyway — on a global
        # board (thousands of postings) this is the difference between minutes
        # and hours per sweep.
        if not location_matches(location, location_filter):
            continue
        time.sleep(1.0)
        description, url = _detail(slug, job.get("id", ""))
        out.append(
            Posting(
                source="smartrecruiters",
                slug=slug,
                company=(job.get("company") or {}).get("name", slug),
                title=job.get("name", ""),
                location=location,
                url=url or f"https://jobs.smartrecruiters.com/{slug}/{job.get('id', '')}",
                department=(job.get("department") or {}).get("label", ""),
                updated_at=job.get("releasedDate", ""),
                description=description,
            )
        )
    return out
