#!/usr/bin/env python3
"""check_template_clean.py — the shared template holds no personal data. PRD §19.2.

    check_template_clean.py [--root .]

This repo is handed to other people. Every copy inherits whatever is committed
here, so one accidental `/setup` run against the template would ship its
author's career history to everyone who ever uses it. This guard makes that
failure loud instead of silent.

It is for the TEMPLATE repo only. A private instance is *supposed* to have a
full `profile/` and a populated tracker — CI skips this check anywhere but the
template (see .github/workflows/ci.yml), and running it by hand in your own
instance is expected to fail. That is not a bug; it means your setup worked.
"""
from __future__ import annotations

import argparse
import os
import sys

# Files that legitimately live in the template's otherwise-empty data dirs.
ALLOWED = {
    "profile/README.md",
    "profile/.gitkeep",
    "profile/companies/.gitkeep",
    "profile/manual-postings/README.md",
    "profile/manual-postings/.gitkeep",
    "queue/.gitkeep",
    "state/seen/.gitkeep",
    "applied/.gitkeep",
}

# Directories that must contain nothing but ALLOWED entries.
GUARDED_DIRS = ["profile", "queue", "state", "applied"]

TRACKER_HEADER = "date,company,title,status,days_since_applied,funnel_stage,next_action,url,dir"


def violations(root: str) -> list[str]:
    found: list[str] = []

    for d in GUARDED_DIRS:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
                if rel not in ALLOWED:
                    found.append(f"personal data in the template: {rel}")

    tracker = os.path.join(root, "tracker.csv")
    if os.path.exists(tracker):
        with open(tracker, encoding="utf-8") as fh:
            rows = [line for line in fh.read().splitlines() if line.strip()]
        if len(rows) > 1:
            found.append(
                f"tracker.csv has {len(rows) - 1} application row(s); the template "
                f"ships the header only"
            )
        elif rows and rows[0].strip() != TRACKER_HEADER:
            found.append("tracker.csv header does not match bin/tracker.py's output")

    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail if the template carries personal data.")
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = parser.parse_args(argv)

    found = violations(args.root)
    if found:
        print(f"FAIL: template is not clean — {len(found)} problem(s):", file=sys.stderr)
        for v in found:
            print(f"  ✗ {v}", file=sys.stderr)
        print(
            "\nIf this is YOUR private instance, this check is not for you — it "
            "guards the shared template only.\nIf this is the template: move the "
            "data to your private instance and remove it here.",
            file=sys.stderr,
        )
        return 1
    print("OK: template carries no personal data", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
