"""Seen-state: the sharded, append-only dedupe index. PRD §6.

Invariants (violating any is a bug):
  * One file per sweep: state/seen/<date>.jsonl. Two runs writing two
    different shards can never conflict.
  * Append-only, monotonic, forever. Nothing here is ever rewritten or
    deleted. It lives on `main`, never in a PR.
  * A posting is marked seen ONLY at a terminal disposition (killed by
    triage, or landed in queue/shortlist/). Never at fetch time —
    mark-at-fetch then crash loses postings silently. A shortlisted role
    later discarded at /tailor needs no new record (PRD §15).
"""
from __future__ import annotations

import glob
import json
import os
from typing import Iterable

from schema import SeenEntry

SEEN_DIR = "state/seen"


def _shard_path(date: str, root: str = ".") -> str:
    return os.path.join(root, SEEN_DIR, f"{date}.jsonl")


def load_seen(root: str = ".") -> set[str]:
    """Return the union of fingerprints across every shard.

    fetch.py calls this once at startup to know what to skip.
    """
    seen: set[str] = set()
    pattern = os.path.join(root, SEEN_DIR, "*.jsonl")
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fp = row.get("fingerprint")
                if fp:
                    seen.add(fp)
    return seen


def load_index(root: str = ".") -> dict[str, dict]:
    """Return fingerprint -> first-seen row, with `date` and `shard` filled in.

    Richer sibling of load_seen() for inspection (bin/seen.py check/audit).
    First occurrence wins: the index is append-only, so the earliest row is
    when the posting was first dispositioned.
    """
    index: dict[str, dict] = {}
    pattern = os.path.join(root, SEEN_DIR, "*.jsonl")
    for path in sorted(glob.glob(pattern)):
        shard_date = os.path.basename(path)[: -len(".jsonl")]
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fp = row.get("fingerprint")
                if fp and fp not in index:
                    row.setdefault("date", shard_date)
                    row["shard"] = os.path.join(SEEN_DIR, os.path.basename(path))
                    index[fp] = row
    return index


def append_seen(date: str, entries: Iterable[SeenEntry], root: str = ".") -> str:
    """Append entries to today's shard, creating it if needed.

    Returns the shard path. Idempotent enough for retries: appending the
    same fingerprint twice is harmless because load_seen() dedupes into a set.
    """
    path = _shard_path(date, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for entry in entries:
            payload = entry.model_dump()
            payload.setdefault("date", date)
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path
