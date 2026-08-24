"""Recruitee board adapter. PRD §4.1.

    https://{slug}.recruitee.com/api/offers/

Public, no auth. The envelope is {"offers": [...]}; a 404 means the slug has
no board. Each offer carries a full `location` string plus structured city /
state / country, an HTML `description` and a second HTML `requirements` block
(concatenated here so the queued JD is complete), and `published_at` /
`created_at` as "YYYY-MM-DD HH:MM:SS UTC" (normalized to ISO for freshness).

Note: Recruitee is common among European scale-ups and thinner on the ground
elsewhere, so whether it is worth a line in your `targets.yaml` depends
entirely on where you are looking. The adapter is wired in either way (PRD
§12); an unused one costs nothing.
"""
from __future__ import annotations

import re

from schema import Posting
from sources._http import get_json

BASE = "https://{slug}.recruitee.com/api/offers/"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _iso(raw: str) -> str:
    """"YYYY-MM-DD HH:MM:SS UTC" -> ISO 8601, so freshness can parse it.

    Left untouched if it doesn't match — an unparseable date fails open
    (kept, unknown age) in the freshness filter.
    """
    raw = (raw or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}( UTC)?", raw):
        return raw.replace(" UTC", "").replace(" ", "T") + "+00:00"
    return raw


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    data = get_json(BASE.format(slug=slug))
    offers = data.get("offers", []) if isinstance(data, dict) else []
    out: list[Posting] = []
    for o in offers:
        # Only live listings; skip drafts, internal, and closed roles.
        if o.get("status") and o.get("status") != "published":
            continue
        location = o.get("location") or ", ".join(
            x for x in (o.get("city", ""), o.get("state_name", ""), o.get("country", "")) if x
        )
        jd = _strip_html(o.get("description", ""))
        reqs = _strip_html(o.get("requirements", ""))
        description = (jd + "\n\n" + reqs).strip() if reqs else jd
        out.append(
            Posting(
                source="recruitee",
                slug=slug,
                company=o.get("company_name", "") or slug,
                title=o.get("title", ""),
                location=location,
                url=o.get("careers_url", "") or o.get("careers_apply_url", ""),
                department=o.get("department", "") or "",
                updated_at=_iso(o.get("published_at", "") or o.get("created_at", "")),
                description=description,
            )
        )
    return out
