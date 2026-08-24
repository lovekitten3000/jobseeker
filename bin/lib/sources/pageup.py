"""PageUp People adapter. PRD §4.1.

PageUp's public candidate site returns a JSON envelope whose `results` field
is an HTML fragment listing the jobs (title + apply link per `<li>`), with a
`count` of total matches. A target's `slug` is the board path segment:

    {instance}/{brand}/{lang}   e.g.  410/fb/en

Read it off a live PageUp URL: careers.pageuppeople.com/410/fb/en/... . Two
quirks the adapter handles: the envelope is only returned as JSON when the
request carries `X-Requested-With: XMLHttpRequest` (otherwise a rendered HTML
page comes back), and the job list carries no location string — so every
posting reaches triage and location scoping happens there rather than at fetch
time. A single-region PageUp board therefore costs nothing; a multi-region one
sends triage roles your `location_filter` would have dropped. Pages are fixed
at 10 items; `count` bounds the paging. Internal calls self-pace at 1s
(fetch.py's ≤1 req/sec/host budget only covers gaps between adapter
invocations).
"""
from __future__ import annotations

import html
import re
import time

from schema import Posting
from sources._http import get_json

BASE = "https://careers.pageuppeople.com/{path}/filter/"
AJAX = {"X-Requested-With": "XMLHttpRequest"}
# One job per <li>: the first job-link anchor carries the apply path and title.
JOB_RE = re.compile(
    r'<a class="job-link"\s+href="(?P<href>/[^"]+/job/\d+/[^"]+)">(?P<title>[^<]+)</a>'
)
MAX_PAGES = 100  # backstop; real boards are far smaller (tens of pages at most)


def fetch(slug: str, location_filter: list[str] | None = None) -> list[Posting]:
    path = slug.strip("/")
    out: list[Posting] = []
    seen: set[str] = set()
    page = 1
    while page <= MAX_PAGES:
        data = get_json(
            BASE.format(path=path), params={"data": "json", "page": page}, headers=AJAX
        )
        if not isinstance(data, dict):
            break
        fragment = data.get("results", "") or ""
        count = data.get("count", 0) or 0
        matches = JOB_RE.finditer(fragment)
        new = 0
        for m in matches:
            href = m.group("href")
            if href in seen:
                continue
            seen.add(href)
            new += 1
            out.append(
                Posting(
                    source="pageup",
                    slug=slug,
                    company=path.split("/")[0],  # instance id; name lives in targets.yaml
                    title=html.unescape(m.group("title")).strip(),
                    location="",  # not in the list; fetch.py filter + triage handle it
                    url="https://careers.pageuppeople.com" + href,
                    department="",
                    updated_at="",
                    description="",
                )
            )
        # Stop when a page adds nothing new (end of list) or we've seen `count`.
        if new == 0 or (count and len(seen) >= count):
            break
        page += 1
        time.sleep(1.0)
    return out
