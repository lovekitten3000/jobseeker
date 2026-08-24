#!/usr/bin/env python3
"""fetch.py — pull postings from ATS public APIs into queue/raw/. PRD §8.1.

    fetch.py [--source ats|all] [--dry-run]

Reads profile/targets.yaml -> lib/sources/<ats>.py. Skips postings outside the
location filter, outside profile/goals.yaml's optional role_filter, or last
updated more than --max-age-days ago (default 30). Dedupes against the union of
state/seen/*.jsonl. Writes one JSON file per posting under queue/raw/.
Never calls a model. Never writes seen-state (that is seen.py, at terminal
disposition only). One broken adapter logs a warning and the sweep continues.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

# Make lib/ importable whether run from repo root or elsewhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "lib"))

import yaml  # noqa: E402

from dedupe import dedupe  # noqa: E402
from freshness import is_fresh  # noqa: E402
from locations import location_matches  # noqa: E402
from roles import load_goals, role_filter as goals_role_filter, title_matches  # noqa: E402
from schema import Posting  # noqa: E402
from seen import load_seen  # noqa: E402
from sources import get_adapter  # noqa: E402

RATE_LIMIT_SECONDS = 1.0  # ≤1 req/sec/host
RAW_DIR = "queue/raw"
MAX_AGE_DAYS = 30  # skip postings not updated within this window (0 disables)


def load_targets(root: str) -> tuple[list[dict], list[str]]:
    """Return (companies, location_filter) from profile/targets.yaml."""
    path = os.path.join(root, "profile", "targets.yaml")
    if not os.path.exists(path):
        print(f"warning: {path} not found; nothing to fetch", file=sys.stderr)
        return [], []
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        print(f"warning: {path} is not a mapping; nothing to fetch", file=sys.stderr)
        return [], []
    return data.get("companies", []) or [], data.get("location_filter", []) or []


def fetch_all(
    targets: list[dict],
    only_source: str | None,
    location_filter: list[str],
    max_age_days: int = MAX_AGE_DAYS,
    role_patterns: list[str] | None = None,
) -> tuple[list[Posting], int, int, int]:
    """Return (postings, adapter_failures, attempted, role_dropped).

    Rate-limited per host by sleeping between calls to the same source.
    `role_dropped` counts postings the optional role filter removed — the sweep
    reports it so an opt-in narrowing is never silent (PRD §19).
    """
    postings: list[Posting] = []
    failures = 0
    attempted = 0
    role_dropped = 0
    last_call: dict[str, float] = {}
    for target in targets:
        ats = target.get("ats")
        slug = target.get("slug")
        if not ats or not slug:
            print(f"warning: skipping malformed target {target!r}", file=sys.stderr)
            continue
        if only_source and only_source != "all" and ats != only_source:
            continue
        attempted += 1
        # Rate limit per source/host.
        wait = RATE_LIMIT_SECONDS - (time.monotonic() - last_call.get(ats, 0.0))
        if wait > 0:
            time.sleep(wait)
        try:
            adapter = get_adapter(ats)
            found = adapter.fetch(slug, location_filter=location_filter)
            located = [p for p in found if location_matches(p.location, location_filter)]
            on_track = [p for p in located if title_matches(p.title, role_patterns)]
            role_dropped += len(located) - len(on_track)
            kept = [p for p in on_track if is_fresh(p.updated_at, max_age_days)]
            postings.extend(kept)
            notes = []
            if len(located) != len(found):
                notes.append(f"{len(found) - len(located)} outside location filter")
            if len(on_track) != len(located):
                notes.append(f"{len(located) - len(on_track)} outside role filter")
            if len(kept) != len(on_track):
                notes.append(f"{len(on_track) - len(kept)} stale (>{max_age_days}d)")
            print(
                f"  {ats}/{slug}: {len(kept)} postings"
                + (f" ({', '.join(notes)})" if notes else ""),
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001 — one dead adapter must not kill the run
            failures += 1
            print(f"warning: adapter {ats}/{slug} failed: {exc}", file=sys.stderr)
        finally:
            last_call[ats] = time.monotonic()
    return postings, failures, attempted, role_dropped


def write_raw(postings: list[Posting], root: str) -> int:
    out_dir = os.path.join(root, RAW_DIR)
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for p in postings:
        fname = f"{p.fingerprint()[:16]}_{p.slugify()}.json"
        # The full fingerprint rides along so downstream steps (shortlist
        # meta.yaml, seen.py) never have to recompute it from possibly-edited
        # company/title/location text. Posting ignores the extra key on load.
        payload = {**p.model_dump(), "fingerprint": p.fingerprint()}
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch ATS postings into queue/raw/.")
    parser.add_argument("--source", default="all", help="ats name or 'all' (default)")
    parser.add_argument("--dry-run", action="store_true", help="fetch + dedupe, write nothing")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=MAX_AGE_DAYS,
        help=f"skip postings last updated more than this many days ago; 0 disables (default: {MAX_AGE_DAYS})",
    )
    parser.add_argument(
        "--ignore-role-filter",
        action="store_true",
        help="ignore profile/goals.yaml role_filter for this run (full coverage)",
    )
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = parser.parse_args(argv)

    targets, location_filter = load_targets(args.root)
    if not targets:
        print("no targets configured", file=sys.stderr)
        return 0

    role_patterns = [] if args.ignore_role_filter else goals_role_filter(load_goals(args.root))

    # Validate location_filter regexes up front. A bad pattern raises re.error
    # inside every per-target block (location_matches runs for all of them),
    # which fetch_all counts as an adapter failure — so a single typo'd regex
    # would trip the "all adapters failed" abort and read as a broken
    # environment. Surface it as the config error it is instead.
    for pattern in location_filter:
        try:
            re.compile(pattern)
        except re.error as exc:
            print(
                f"error: invalid location_filter regex {pattern!r} in "
                f"profile/targets.yaml: {exc}",
                file=sys.stderr,
            )
            return 2
    for pattern in role_patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            print(
                f"error: invalid role_filter regex {pattern!r} in "
                f"profile/goals.yaml: {exc}",
                file=sys.stderr,
            )
            return 2

    seen = load_seen(args.root)
    print(f"loaded {len(seen)} seen fingerprints", file=sys.stderr)
    if not seen:
        print(
            "warning: seen index is empty (state/seen/ has no shards) — nothing "
            "from prior sweeps will be deduped. Expected on the first run only; "
            "otherwise a past sweep skipped its mark step. Run "
            "`bin/seen.py audit` to verify.",
            file=sys.stderr,
        )

    postings, failures, attempted, role_dropped = fetch_all(
        targets,
        args.source,
        location_filter,
        max_age_days=args.max_age_days,
        role_patterns=role_patterns,
    )
    if attempted and failures == attempted:
        print(
            f"error: all {attempted} adapter fetch(es) failed — nothing was "
            "fetched. Check the environment allowlist (docs/ENVIRONMENT.md §1) "
            "before trusting this run. Exiting non-zero so an unattended sweep "
            "cannot mistake a broken environment for a quiet night.",
            file=sys.stderr,
        )
        return 2
    fresh = dedupe(postings, seen)
    print(
        f"fetched {len(postings)} postings, {len(fresh)} new after dedupe, "
        f"{failures} adapter failure(s)",
        file=sys.stderr,
    )
    if role_dropped:
        # Never silent: this is the one narrowing that can drop a role triage
        # would have kept, so the count reaches the sweep's report (PRD §19).
        print(
            f"role_filter dropped {role_dropped} posting(s) before triage "
            f"(profile/goals.yaml; --ignore-role-filter for full coverage)",
            file=sys.stderr,
        )

    if args.dry_run:
        print("dry-run: not writing queue/raw/", file=sys.stderr)
        return 0

    written = write_raw(fresh, args.root)
    print(f"wrote {written} postings to {RAW_DIR}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
