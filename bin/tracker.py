#!/usr/bin/env python3
"""tracker.py — regenerate tracker.csv from meta.yaml files. PRD §8.4, G4.

    tracker.py [--root .] [-o tracker.csv]

The tracker is DERIVED, never maintained (principle 3.2). Delete tracker.csv,
regenerate, and get a byte-identical file. Scans applied/*/meta.yaml and
queue/ready/*/meta.yaml. Derives days_since_applied, status (auto-ghosted after
config.tracker.ghost_days silent days), next_action, funnel_stage.

No Google Sheets push — GitHub renders a committed CSV as a sortable table on
desktop and mobile for free (PRD §8.4).
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
from datetime import date, datetime

import yaml

COLUMNS = [
    "date",
    "company",
    "title",
    "status",
    "days_since_applied",
    "funnel_stage",
    "next_action",
    "url",
    "dir",
]

# Positive statuses the human sets in meta.yaml via /log. Silence -> ghosted.
FUNNEL = {
    "shortlisted": 0,
    "kept": 0,
    "queued": 0,
    "applied": 1,
    "ghosted": 1,
    "reply": 2,
    "screen": 3,
    "onsite": 4,
    "offer": 5,
    "rejected": -1,
    "withdrawn": -1,
}

NEXT_ACTION = {
    "shortlisted": "pick keeps with /choose",
    "kept": "run /tailor",
    "queued": "review at Gate 2",
    "applied": "wait",
    "ghosted": "follow up or drop",
    "reply": "schedule screen",
    "screen": "prep + confirm onsite",
    "onsite": "send thank-you, await decision",
    "offer": "negotiate / decide",
    "rejected": "—",
    "withdrawn": "—",
}


def _today(explicit: str | None) -> date:
    if explicit:
        return datetime.strptime(explicit, "%Y-%m-%d").date()
    return date.today()


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def load_config(root: str) -> dict:
    path = os.path.join(root, "profile", "config.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def collect_rows(root: str, ghost_days: int, today: date) -> list[dict]:
    rows: list[dict] = []
    patterns = [
        os.path.join(root, "applied", "*", "meta.yaml"),
        os.path.join(root, "queue", "ready", "*", "meta.yaml"),
    ]
    seen_dirs: set[str] = set()
    for pattern in patterns:
        for meta_path in sorted(glob.glob(pattern)):
            dir_name = os.path.basename(os.path.dirname(meta_path))
            if dir_name in seen_dirs:
                continue
            seen_dirs.add(dir_name)
            with open(meta_path, encoding="utf-8") as fh:
                meta = yaml.safe_load(fh) or {}

            status = str(meta.get("status", "queued")).strip().lower()
            applied_on = _parse_date(meta.get("applied") or meta.get("date"))
            days = (today - applied_on).days if applied_on else ""

            # Auto-ghost: applied, silent past ghost_days, no positive event.
            if status == "applied" and isinstance(days, int) and days >= ghost_days:
                status = "ghosted"

            rows.append(
                {
                    "date": meta.get("date", applied_on.isoformat() if applied_on else ""),
                    "company": meta.get("company", ""),
                    "title": meta.get("title", ""),
                    "status": status,
                    "days_since_applied": days,
                    "funnel_stage": FUNNEL.get(status, 0),
                    "next_action": NEXT_ACTION.get(status, "review"),
                    "url": meta.get("url", ""),
                    "dir": dir_name,
                }
            )
    # Deterministic order so regeneration is byte-identical (G4 / Phase 7 test).
    rows.sort(key=lambda r: (str(r["date"]), r["dir"]))
    return rows


def write_csv(rows: list[dict], out_path: str) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate tracker.csv from meta.yaml files.")
    parser.add_argument("--root", default=".")
    parser.add_argument("-o", "--out", default=None)
    parser.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD)")
    args = parser.parse_args(argv)

    config = load_config(args.root)
    ghost_days = int((config.get("tracker", {}) or {}).get("ghost_days", 21))
    today = _today(args.today)
    out_path = args.out or os.path.join(args.root, "tracker.csv")

    rows = collect_rows(args.root, ghost_days, today)
    write_csv(rows, out_path)
    print(f"wrote {out_path} — {len(rows)} row(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
