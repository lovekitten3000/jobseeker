"""Workday CXS adapter. PRD §4.1.

Workday's public job-search API is POST-only and per-tenant, so a target's
`slug` encodes the three parts the URL needs, slash-separated:

    tenant/dc/site        e.g.  commbank/wd3/CommBankCareers

{tenant} is the Workday tenant, {dc} its data-center subdomain (wd1, wd3,
wd5, ...), {site} the external career-site path. Read them off a company's
Workday careers URL: https://{tenant}.{dc}.myworkdayjobs.com/{site}.

The list endpoint carries no description and reports multi-location roles as
"N Locations" instead of place names, so this adapter:
  1. pages the list (POST, 20/page) up to MAX_PAGES,
  2. keeps postings whose `locationsText` matches the location filter — a
     precise single-location string like "<City>, <Country>". Multi-location
     "N Locations" rows carry no place name and are skipped: the one coverage
     gap, and it is logged when it bites,
  3. fetches each kept posting's detail for the real location, description,
     apply URL, and posted date (bounded by MAX_DETAIL).

Internal calls self-pace at 1s: fetch.py's ≤1 req/sec/host budget only covers
the gap between adapter invocations, not requests made inside one.
"""
from __future__ import annotations

import re
import sys
import time

from locations import location_matches
from schema import Posting
from sources._http import get_json, post_json, session

BASE = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
PAGE_SIZE = 20
MAX_PAGES = 50            # cap listings scanned per board (50 * 20 = 1000)
MAX_DETAIL = 80           # cap per-board detail calls (located postings only)
PACE_SECONDS = 1.0        # self-pacing between this adapter's own requests


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _collect_location_facets(
    facets: list, location_filter: list[str] | None
) -> dict[str, list[str]]:
    """Map facetParameter -> [value ids] for leaf values matching the filter.

    Workday nests location facets: a group node carries its own
    `facetParameter` and a `values` list of either leaves ({descriptor, id,
    count}) or further sub-groups (each with its own `facetParameter`). A leaf
    is applied under the `facetParameter` of the group that directly contains
    it, so we recurse and attribute each match to its parent group.
    """
    found: dict[str, list[str]] = {}

    def walk(node: dict) -> None:
        fp = node.get("facetParameter")
        for v in node.get("values", []) or []:
            if v.get("values"):
                walk(v)
            elif v.get("id") and location_matches(v.get("descriptor", ""), location_filter):
                found.setdefault(fp, []).append(v["id"])

    for f in facets or []:
        walk(f)
    return found


def _discover_location_facets(
    base: str, location_filter: list[str] | None
) -> dict[str, list[str]]:
    """Find the applied-facet payload that scopes a board to your region server-side.

    Globally-sorted boards (the giants list 2k–5k roles) bury in-region roles
    below the scan window, so a blind page-and-filter misses them. Instead,
    read the board's own location facets and apply the ones whose descriptor
    matches the location filter — the board then returns only in-region roles
    and every one is in the window. Returns {} when the board exposes no
    matching facet (a board that is already single-region, or one with no
    country facet at all), and the caller falls back to the plain paged scan.
    Applies exactly ONE facet parameter: Workday ANDs across different
    parameters, so mixing a country facet with a city facet would intersect to
    just that city. Prefer a country-level parameter (broadest); else the one
    with the most matches.
    """
    if not location_filter:
        return {}
    try:
        data = post_json(
            base + "/jobs", {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
        )
    except Exception:  # noqa: BLE001 — discovery is best-effort; fall back to scan
        return {}
    if not isinstance(data, dict):
        return {}
    found = _collect_location_facets(data.get("facets", []), location_filter)
    if not found:
        return {}
    for fp in found:
        if "country" in (fp or "").lower():
            return {fp: found[fp]}
    best = max(found, key=lambda k: len(found[k]))
    return {best: found[best]}


def _parse_slug(slug: str) -> tuple[str, str, str]:
    parts = [p for p in slug.split("/") if p]
    if len(parts) != 3:
        raise ValueError(
            f"workday slug must be 'tenant/dc/site', read off the board's URL "
            f"https://<tenant>.<dc>.myworkdayjobs.com/<site> — got {slug!r}"
        )
    return parts[0], parts[1], parts[2]


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    tenant, dc, site = _parse_slug(slug)
    base = BASE.format(tenant=tenant, dc=dc, site=site)

    # One session per board: the list-paging POSTs and the per-posting detail
    # GETs then share a connection pool and cookie jar, so any clearance cookie
    # Workday's edge hands back persists across the board's requests instead of
    # being thrown away on each call (PRD §4.1; sources/_http.py).
    with session():
        # 0. Try to scope the board server-side via its location facets.
        #    Unlocks globally-sorted giants whose in-region roles sit below the
        #    scan window; empty for boards that are already single-region, which
        #    then fall back to the plain paged scan below.
        applied = _discover_location_facets(base, location_filter)
        if location_filter:
            time.sleep(PACE_SECONDS)  # pace the discovery call against paging
        if applied:
            print(
                f"  workday/{slug}: scoping to your locations via facet {applied}",
                file=sys.stderr,
            )

        # 1. Page the list endpoint.
        #    Some tenants report the real `total` only on the first page and
        #    0 on every page after it. Trusting each page's `total` therefore
        #    breaks after page 2 and loses most of the board. Latch the largest
        #    total ever seen so paging runs until the postings actually run out
        #    (empty page) or MAX_PAGES.
        listings: list[dict] = []
        offset = 0
        total = 0
        for _ in range(MAX_PAGES):
            data = post_json(
                base + "/jobs",
                {"appliedFacets": applied, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
            )
            if not isinstance(data, dict):
                break
            page = data.get("jobPostings", []) or []
            listings.extend(page)
            offset += len(page)
            total = max(total, data.get("total", 0) or 0)
            if not page or offset >= total:
                break
            time.sleep(PACE_SECONDS)

        # 2. Keep postings the location filter accepts from `locationsText` alone.
        #    "N Locations" aggregates carry no place name -> dropped here.
        kept = [j for j in listings if location_matches(j.get("locationsText", ""), location_filter)]
        if len(kept) > MAX_DETAIL:
            print(
                f"  workday/{slug}: {len(kept)} located postings exceed the "
                f"{MAX_DETAIL} detail-fetch cap; {len(kept) - MAX_DETAIL} skipped "
                "this run",
                file=sys.stderr,
            )
            kept = kept[:MAX_DETAIL]

        # 3. Fetch detail for the precise location, description, URL, and date.
        out: list[Posting] = []
        for j in kept:
            ep = j.get("externalPath", "")
            if not ep:
                continue
            time.sleep(PACE_SECONDS)
            try:
                detail = get_json(base + ep)
            except Exception:  # noqa: BLE001 — one dead posting must not kill the board
                continue
            info = detail.get("jobPostingInfo", {}) if isinstance(detail, dict) else {}
            if not isinstance(info, dict):
                info = {}
            out.append(
                Posting(
                    source="workday",
                    slug=slug,
                    company=tenant,
                    title=info.get("title", "") or j.get("title", ""),
                    location=info.get("location", "") or j.get("locationsText", ""),
                    url=info.get("externalUrl", "") or (base + ep),
                    department="",
                    updated_at=info.get("startDate", "") or "",
                    description=_strip_html(info.get("jobDescription", "")),
                )
            )
    return out
