"""Oracle Recruiting Cloud (Fusion CX) adapter. PRD §4.1.

Oracle's public candidate-experience REST API. A target's `slug` encodes the
two parts the URL needs, slash-separated:

    host/site        e.g.  ebuu.fa.ap1.oraclecloud.com/CX

{host} is the Fusion pod host, {site} the candidate-experience site number.
Read them off a company's Oracle careers URL:
https://{host}/hcmUI/CandidateExperience/en/sites/{site}/jobs.

The list endpoint carries the title, primary location, posted date and a short
description inline, so no per-posting detail call is needed. `TotalJobsCount`
drives pagination. Internal calls self-pace at 1s: fetch.py's ≤1 req/sec/host
budget only covers the gap between adapter invocations, not requests made
inside one.
"""
from __future__ import annotations

import re
import time

from locations import location_matches
from schema import Posting
from sources._http import get_json

LIST = (
    "https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    "?onlyData=true&expand=requisitionList.secondaryLocations"
    "&finder=findReqs;siteNumber={site},limit={limit},offset={offset}"
    ",sortBy=POSTING_DATES_DESC"
)
PAGE_SIZE = 100
MAX_PAGES = 20  # cap: 100 * 20 = 2000 requisitions per board


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _parse_slug(slug: str) -> tuple[str, str]:
    parts = [p for p in slug.split("/") if p]
    if len(parts) != 2:
        raise ValueError(
            f"oracle slug must be 'host/site' (e.g. ebuu.fa.ap1.oraclecloud.com/"
            f"CX), got {slug!r}"
        )
    return parts[0], parts[1]


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    host, site = _parse_slug(slug)
    company = host.split(".")[0]  # pod label; targets.yaml `name` is the display
    out: list[Posting] = []
    offset = 0
    total = 0
    for _ in range(MAX_PAGES):
        data = get_json(LIST.format(host=host, site=site, limit=PAGE_SIZE, offset=offset))
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        item = items[0]
        total = item.get("TotalJobsCount", 0) or 0
        reqs = item.get("requisitionList", []) or []
        if not reqs:
            break
        for q in reqs:
            location = q.get("PrimaryLocation", "") or ""
            # The list already carries the location, so skip postings the filter
            # would drop — no detail call to save here, but it keeps the queue
            # clean the same way smartrecruiters does.
            if not location_matches(location, location_filter):
                continue
            description = _strip_html(
                " ".join(
                    s
                    for s in (
                        q.get("ShortDescriptionStr", ""),
                        q.get("ExternalResponsibilitiesStr", ""),
                        q.get("ExternalQualificationsStr", ""),
                    )
                    if s
                )
            )
            job_id = q.get("Id", "") or ""
            out.append(
                Posting(
                    source="oracle",
                    slug=slug,
                    company=company,
                    title=q.get("Title") or "",
                    location=location,
                    url=(
                        f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}"
                        f"/job/{job_id}"
                    ),
                    department=q.get("JobFamily") or q.get("Organization") or "",
                    updated_at=q.get("PostedDate") or "",
                    description=description,
                )
            )
        offset += len(reqs)
        if offset >= total:
            break
        time.sleep(1.0)
    return out
