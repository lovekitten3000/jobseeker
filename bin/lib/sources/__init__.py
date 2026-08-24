"""ATS adapters. One file per provider. PRD §4.1, §8.1.

Each module exposes `fetch(slug, location_filter=None) -> list[Posting]`.
`location_filter` (regexes from targets.yaml) is advisory: fetch.py applies
it to every adapter's output anyway, so adapters only use it to avoid
per-posting follow-up requests they can tell are wasted (smartrecruiters).
Endpoint shapes drift; when one breaks, it is one file to fix, and fetch.py
keeps going.
"""
from __future__ import annotations

from importlib import import_module

# Registry of adapter name -> module path. Add a line here to wire in a new ATS.
ADAPTERS = {
    "greenhouse": "sources.greenhouse",
    "lever": "sources.lever",
    "ashby": "sources.ashby",
    "workable": "sources.workable",
    "smartrecruiters": "sources.smartrecruiters",
    "recruitee": "sources.recruitee",
    "workday": "sources.workday",
    "oracle": "sources.oracle",
    "pageup": "sources.pageup",
    "teamtailor": "sources.teamtailor",
}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise KeyError(f"unknown ATS adapter: {name!r}. known: {sorted(ADAPTERS)}")
    return import_module(ADAPTERS[name])
