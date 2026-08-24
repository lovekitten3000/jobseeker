#!/usr/bin/env python3
"""seen.py — CLI for the seen-state dedupe index. PRD §6.

    seen.py status  [--root .]
    seen.py check   [--root .] [ENTRY ...] [--fingerprint FP]
                    [--company C --title T [--location L]]
    seen.py mark    --disposition {killed,shortlisted,near_miss} [--date YYYY-MM-DD]
                    [--root .] ENTRY [ENTRY ...]
    seen.py audit   [--root .] [--date YYYY-MM-DD]

An ENTRY is a raw posting JSON from queue/raw/, a queue meta.yaml, or a queue
directory containing one — so a seen record can be repaired from the shortlist
itself after the raw files are gone (fresh VM). When a meta.yaml carries a
`fingerprint:` field (the sweep writes one), that exact fingerprint is used;
recomputing from meta text is the fallback.

The index lives in state/seen/<date>.jsonl on `main`, one append-only shard
per sweep day (PRD §6). fetch.py dedupes against it at fetch time; this tool
is how the sweep WRITES it (mark, at terminal disposition only — never at
fetch) and how a human or agent VERIFIES it (status, check, audit).

`mark` is idempotent: fingerprints already anywhere in the index are skipped,
so a retried sweep step cannot double-write. `audit` cross-checks the queue
against the index and exits 1 if a swept role has no seen record — the exact
failure mode that lets the next sweep re-triage the same job. With `--date`
it also checks the reverse direction for that day's shard: every entry marked
`shortlisted` or `near_miss` (both name a role queued to queue/shortlist) must
still have a queue (or applied/) directory, catching a run that marked roles
seen and then crashed before recording them anywhere.

Seen-state is a fact, not a proposal: commit the shard to `main`, never to a
PR (red line 8).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob as _glob
import json
import os
import sys

# Make lib/ importable whether run from repo root or elsewhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "lib"))

import yaml  # noqa: E402

from schema import Posting, SeenEntry  # noqa: E402
from seen import SEEN_DIR, append_seen, load_index  # noqa: E402

RAW_DIR = "queue/raw"
QUEUE_DIRS = ("queue/shortlist", "queue/ready")


def _load_posting(path: str) -> Posting:
    with open(path, encoding="utf-8") as fh:
        return Posting.model_validate(json.load(fh))


def _load_meta(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        meta = yaml.safe_load(fh) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: meta.yaml is not a mapping")
    return meta


def _meta_fingerprint(meta: dict, path: str = "") -> tuple[Posting, str]:
    """(posting, fingerprint) from a queue meta.yaml dict.

    Prefers the stored `fingerprint:` (exact, survives pretty-printed company
    names); falls back to recomputing from company/title/location text.
    """
    company = str(meta.get("company", "") or "")
    title = str(meta.get("title", "") or "")
    if not company or not title:
        raise ValueError(f"{path or 'meta'}: meta.yaml needs company and title")
    p = Posting(
        source=str(meta.get("source", "meta") or "meta"), slug="meta",
        company=company, title=title,
        location=str(meta.get("location", "") or ""),
    )
    fp = str(meta.get("fingerprint", "") or "") or p.fingerprint()
    return p, fp


def _load_entry(path: str) -> tuple[Posting, str]:
    """(posting, fingerprint) from a raw JSON, a meta.yaml, or a queue dir."""
    if os.path.isdir(path):
        path = os.path.join(path, "meta.yaml")
    if path.endswith((".yaml", ".yml")):
        return _meta_fingerprint(_load_meta(path), path)
    p = _load_posting(path)
    return p, p.fingerprint()


def _describe(row: dict) -> str:
    return (
        f"seen {row.get('date', '?')} ({row.get('disposition', '?')}) "
        f"— {row.get('company', '?')} · {row.get('title', '?')} "
        f"[{row.get('shard', '?')}]"
    )


# ── status ─────────────────────────────────────────────────────────────────


def cmd_status(args: argparse.Namespace) -> int:
    pattern = os.path.join(args.root, SEEN_DIR, "*.jsonl")
    shards = sorted(_glob.glob(pattern))
    index = load_index(args.root)
    if not shards:
        print(f"seen index is empty: no shards under {SEEN_DIR}/")
        print("(first run, or seen-state was never written — run `seen.py audit`)")
        return 0
    print(f"{len(shards)} shard(s), {len(index)} unique fingerprint(s)")
    for path in shards:
        with open(path, encoding="utf-8") as fh:
            rows = [ln for ln in fh if ln.strip()]
        print(f"  {os.path.join(SEEN_DIR, os.path.basename(path))}: {len(rows)} entr(ies)")
    by_disposition: dict[str, int] = {}
    for row in index.values():
        d = row.get("disposition", "?")
        by_disposition[d] = by_disposition.get(d, 0) + 1
    for d in sorted(by_disposition):
        print(f"  {d}: {by_disposition[d]}")
    return 0


# ── check ──────────────────────────────────────────────────────────────────


def cmd_check(args: argparse.Namespace) -> int:
    index = load_index(args.root)
    queries: list[tuple[str, str]] = []  # (label, fingerprint)
    for path in args.files:
        p, fp = _load_entry(path)
        queries.append((f"{p.company} · {p.title}", fp))
    if args.fingerprint:
        queries.append((args.fingerprint[:16], args.fingerprint))
    if args.company and args.title:
        p = Posting(
            source="check", slug="check",
            company=args.company, title=args.title, location=args.location or "",
        )
        queries.append((f"{args.company} · {args.title}", p.fingerprint()))
    if not queries:
        print("nothing to check: pass FILE.json, --fingerprint, or --company/--title",
              file=sys.stderr)
        return 2
    unseen = 0
    for label, fp in queries:
        row = index.get(fp)
        if row:
            print(f"SEEN    {label}: {_describe(row)}")
        else:
            unseen += 1
            print(f"UNSEEN  {label}: not in index — a sweep would triage this")
    return 1 if unseen else 0


# ── mark ───────────────────────────────────────────────────────────────────


def cmd_mark(args: argparse.Namespace) -> int:
    index = load_index(args.root)
    date = args.date or _dt.date.today().isoformat()
    entries: list[SeenEntry] = []
    skipped = 0
    for path in args.files:
        p, fp = _load_entry(path)
        if fp in index:
            skipped += 1
            print(f"skip (already {_describe(index[fp])}): {p.company} · {p.title}",
                  file=sys.stderr)
            continue
        entries.append(
            SeenEntry(
                fingerprint=fp,
                company=p.company,
                title=p.title,
                disposition=args.disposition,
                date=date,
            )
        )
        # Guard against the same posting listed twice on one command line.
        index[fp] = {"disposition": args.disposition, "date": date,
                     "company": p.company, "title": p.title, "shard": "(this run)"}
    if entries:
        shard = append_seen(date, entries, args.root)
        print(f"marked {len(entries)} {args.disposition} in {os.path.relpath(shard, args.root)}"
              + (f" ({skipped} already seen, skipped)" if skipped else ""))
        print("commit this shard to main — never to a PR (red line 8)")
    else:
        print(f"nothing to mark ({skipped} already seen)")
    return 0


# ── audit ──────────────────────────────────────────────────────────────────


def _swept_meta_dirs(root: str):
    """Yield (dir, meta) for queue entries that came from a sweep.

    A meta.yaml counts as swept when it has a `swept:` date or a structured
    triage score. Manual finds (/add) have neither and are exempt — they were
    never fetched, so seen-state doesn't apply to them.
    """
    for base in QUEUE_DIRS:
        for meta_path in sorted(_glob.glob(os.path.join(root, base, "*", "meta.yaml"))):
            try:
                with open(meta_path, encoding="utf-8") as fh:
                    meta = yaml.safe_load(fh) or {}
            except yaml.YAMLError:
                continue
            if not isinstance(meta, dict):
                continue
            if meta.get("swept") or isinstance(meta.get("triage"), dict):
                yield os.path.dirname(meta_path), meta


def _recorded_fingerprints(root: str) -> set[str]:
    """Fingerprints of every queue/ and applied/ entry with a meta.yaml."""
    fps: set[str] = set()
    for base in QUEUE_DIRS + ("applied",):
        for meta_path in sorted(_glob.glob(os.path.join(root, base, "*", "meta.yaml"))):
            try:
                meta = _load_meta(meta_path)
                _, fp = _meta_fingerprint(meta, meta_path)
            except (yaml.YAMLError, ValueError):
                continue
            fps.add(fp)
    return fps


def cmd_audit(args: argparse.Namespace) -> int:
    index = load_index(args.root)
    problems = 0

    for entry_dir, meta in _swept_meta_dirs(args.root):
        company = str(meta.get("company", "") or "")
        title = str(meta.get("title", "") or "")
        if not company or not title:
            print(f"WARN  {os.path.relpath(entry_dir, args.root)}: meta.yaml has no "
                  "company/title; cannot verify seen-state")
            problems += 1
            continue
        rel = os.path.relpath(entry_dir, args.root)
        _, fp = _meta_fingerprint(meta, rel)
        if fp not in index:
            problems += 1
            print(f"MISS  {rel}: swept role has no seen record — the next sweep "
                  "WILL re-triage it. "
                  f"Fix: python3 bin/seen.py mark --disposition shortlisted {rel}")

    # Reverse check (--date): every `shortlisted` or `near_miss` row in that
    # day's shard must still be recorded somewhere durable — queue/shortlist,
    # queue/ready, or applied/. Both dispositions name a role the sweep queued
    # to queue/shortlist (a survivor, or a sub-threshold near miss surfaced for
    # Gate 1); only `killed` roles are queued nowhere. A row with no directory
    # means the run marked the role seen and then crashed before writing it
    # anywhere: seen, never queued, gone silently (PRD §6) — exactly what
    # mark-last exists to prevent.
    if args.date:
        shard_path = os.path.join(args.root, SEEN_DIR, f"{args.date}.jsonl")
        recorded = _recorded_fingerprints(args.root)
        if os.path.exists(shard_path):
            with open(shard_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("disposition") not in ("shortlisted", "near_miss"):
                        continue
                    if row.get("fingerprint") not in recorded:
                        problems += 1
                        print(f"LOST  {row.get('company', '?')} · {row.get('title', '?')}: "
                              f"marked {row.get('disposition', '?')} in "
                              f"{os.path.relpath(shard_path, args.root)} "
                              "but no queue/ or applied/ entry exists — seen but never "
                              "queued; it will never be re-triaged. Restore its "
                              "queue/shortlist/<slug>/ directory (jd.md + meta.yaml).")

    raw_leftovers = sorted(_glob.glob(os.path.join(args.root, RAW_DIR, "*.json")))
    if raw_leftovers:
        print(f"INFO  {len(raw_leftovers)} posting(s) still in {RAW_DIR}/ — an "
              "interrupted sweep; they will be re-fetched and re-triaged next run "
              "(by design: mark-at-fetch loses postings, PRD §6)")

    if not index and not problems:
        print("seen index is empty and the queue has no swept entries — nothing to audit")
    elif not problems:
        print(f"OK — every swept queue entry has a seen record ({len(index)} fingerprints)")
    return 1 if problems else 0


# ── entrypoint ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and write the seen-state dedupe index.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="shard and disposition counts")
    p_status.add_argument("--root", default=".")
    p_status.set_defaults(fn=cmd_status)

    p_check = sub.add_parser("check", help="is this posting already seen?")
    p_check.add_argument("files", nargs="*", metavar="ENTRY",
                         help="raw posting JSON, queue meta.yaml, or queue dir")
    p_check.add_argument("--fingerprint")
    p_check.add_argument("--company")
    p_check.add_argument("--title")
    p_check.add_argument("--location", default="")
    p_check.add_argument("--root", default=".")
    p_check.set_defaults(fn=cmd_check)

    p_mark = sub.add_parser("mark", help="append terminal dispositions to today's shard")
    p_mark.add_argument("files", nargs="+", metavar="ENTRY",
                        help="raw posting JSON, queue meta.yaml, or queue dir")
    p_mark.add_argument("--disposition", required=True,
                        choices=["killed", "shortlisted", "near_miss"])
    p_mark.add_argument("--date", help="shard date, default today (YYYY-MM-DD)")
    p_mark.add_argument("--root", default=".")
    p_mark.set_defaults(fn=cmd_mark)

    p_audit = sub.add_parser("audit", help="cross-check queue/ against the index")
    p_audit.add_argument("--root", default=".")
    p_audit.add_argument("--date", help="also reverse-check this day's shard: every "
                         "shortlisted or near_miss row must have a queue/ or applied/ entry")
    p_audit.set_defaults(fn=cmd_audit)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
