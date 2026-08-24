---
name: next
description: Answers "what should I do now?" Reads the repo state (queue, manual postings, tracker, targets, open branches) and gives one prioritized, concrete next action plus a short list of everything else pending. Changes nothing except regenerating the derived tracker.
---

# /next — where am I, what do I do (PRD §14)

The user should never have to remember how this system works. Read the state,
tell them the single next action, list the rest. Be brief: this is a glance,
not a report. Change nothing (regenerating `tracker.csv` is allowed — it's
derived, not a decision).

## Read, in order

0. **Is the system set up at all?** If `profile/goals.yaml` is missing, that is
   the top action, ahead of everything below: *"Run `/setup` — without
   `profile/goals.yaml` nothing knows what job you're looking for, and triage
   falls back to scoring roles by how much they resemble your last one."* If
   `goals.yaml` exists but `profile/evidence-bank.md` doesn't, the action is
   `/setup` to continue the interview.
0b. **Does the bank hold together?** If `profile/evidence-bank.md` exists, run
   `python3 bin/validate.py --lint-bank`. A failure is a top-three action and
   the message says which: an angle nothing proves, an angle with no claim, or
   an entry citing an angle the bank never declared (PRD §21). The fix is a
   short `/setup`-style pass over `## Angles`, not a rewrite — say that.
1. **Drafts awaiting submission** — `queue/ready/*/meta.yaml` on `main` (and
   this branch, if different). Each is a tailored role the human has not
   applied to yet. Sort by `closes:` date; a role closing soon is always the
   top action.
2. **Shortlisted roles awaiting a pick or a tailor** — `queue/shortlist/*/
   meta.yaml` on `main` (pull first). `status: shortlisted` (survivors) and
   `status: near_miss` (below-threshold roles the sweep surfaced for the human
   to judge) both mean nobody has picked yet: the action is `/choose` in a
   fresh session (Gate 1). `status: kept` entries mean the pick happened but
   `/tailor` hasn't run: the action is `/tailor`.
3. **In-flight branches / open PRs** — `git branch -r` for `add/*`, and open
   PRs. An `add/*` branch with drafts not yet walked through is a `/review`
   action; drafts in `queue/ready/` not yet walked through are a `/review`
   action.
4. **Manual postings on hold** — `profile/manual-postings/*.md` with
   `status: new` or `status: hold`. Each needs a decision: pursue via `/add`
   flow, or pass.
5. **The tracker** — run `python3 bin/tracker.py`, read `tracker.csv`. Surface
   anything with a `next_action`, anything freshly `ghosted`, and any positive
   status the human may want to act on.
6. **The sweep's fuel** — if `profile/targets.yaml` has no companies, say so:
   the nightly sweep has nothing to watch, and the system is paste-driven
   (`/add`) until careers-page URLs are added.
7. **Track health** — compare the `track:` values across recent
   `queue/shortlist/` and `applied/` entries against the tracks in
   `profile/goals.yaml`. A track that has produced nothing at all is worth one
   line: its `titles` may be too narrow, or no company in `targets.yaml` hires
   for it. Report it; never edit `goals.yaml` yourself.

## Output shape

```
NEXT: <the one thing to do now, with the exact command or link>

Also pending:
- <item> — <why / by when>
- ...

Quiet: <one line on what needs nothing, e.g. "3 applied roles, none stale">
```

If truly nothing is pending, say so and suggest the one thing that would make
tomorrow better (usually: add a company to `targets.yaml`, or `/add` a posting
they've been sitting on).
