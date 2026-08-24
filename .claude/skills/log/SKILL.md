---
name: log
description: Record a status change in ~2 minutes. Moves a queued role to applied/ after the human submits, or bumps an application's status (reply, screen, onsite, offer, rejected). Then regenerates tracker.csv. Never hand-edit tracker.csv.
---

# /log — status updates (PRD §8.4, G4)

The tracker is derived, never maintained. You never hand-edit `tracker.csv`; you
edit `meta.yaml` and regenerate. A status change costs one `/log` line
(~2 min/week). Silence needs no input — the ghosted timer handles it (G4).

## Two things /log does

### 1. "I applied to <role>"
The human submitted in their own browser. Promote the queued draft:
- `git mv queue/ready/<slug>/ applied/<date>_<slug>/`
- In `applied/<date>_<slug>/meta.yaml` set:
  `status: applied` and `applied: <today>` (and `date:` if unset).
- Regenerate and commit (below). Sweep-path roles live on `main`, so the
  commit is the record — push it. A role from an `/add` branch still has its
  PR: the human **merges it** themselves — the merge means "I applied"
  (PRD §6, §18).

### 2. "<role> → <event>"
A positive event happened. Set `status:` in the role's `meta.yaml` to one of:
`reply`, `screen`, `onsite`, `offer`, `rejected`, `withdrawn`.
Only positive events need logging. Forgetting degrades to `ghosted`, which is
almost always just true.

## Always, after any change
```
python3 bin/tracker.py            # applied/ + queue/ready/ -> tracker.csv
git add applied/ queue/ tracker.csv
git commit -m "log: <role> -> <status>"
```
(The `git add` covers the moved directory, the edited `meta.yaml`, and the
regenerated `tracker.csv` — they all live under those paths.)
`tracker.csv` must never appear in a hand-authored commit — only as
tracker.py's output. Delete it, regenerate, and you get a byte-identical file.

## Never
- Never hand-edit `tracker.csv`.
- Never invent a status the human didn't report.
