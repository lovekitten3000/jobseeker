---
name: tailor
description: Resume and cover development, on demand. Run in a fresh session on main after /choose. Develops every shortlisted role marked kept (or the roles the human names); only those get the expensive tailoring pass, reviewed live in the same session. Never submits.
---

# /tailor — develop the keeps (PRD §15, §18)

The sweep ended at a shortlist on `main`, and `/choose` (Gate 1) recorded
which roles are worth the spend. Only those roles get an Opus tailoring run.
Because the human is sitting right here, the Gate 2 walkthrough happens live
in this session, `/add`-style.

Run this in a fresh session on `main`. Start with
`git checkout main && git pull origin main` so `/choose`'s picks are present.

## Step 0 — check which environment you're in

Company research (PRD §16) needs the open web, and the locked sweep
environment only allows the five ATS hosts. Probe before spending anything:

```
curl -sI --max-time 5 https://example.com >/dev/null && echo open || echo locked
```

- **open** → research will work; carry on silently.
- **locked** → tell the human FIRST, before any tailoring: *"This session is
  in the locked sweep environment, so company research will be skipped and
  covers will open on the role (or your hand-written note). Continue anyway,
  or start a fresh /tailor session in the `jobseeker-interactive` environment
  (see docs/ENVIRONMENT.md)?"* Respect their choice; do not silently proceed.
  If they continue, note "research skipped — locked environment" in the
  closing report for each developed role.

## Step 1 — establish the keeps

The normal case: `/choose` already ran, and the keeps are every
`queue/shortlist/<slug>/` whose `meta.yaml` says `status: kept`. List them
with their triage scores, confirm in one line ("developing these <n>:"), and
go — do not re-ask a question Gate 1 already answered.

Fallbacks, in order:
- The human names keeps in the prompt ("tailor torrens and origin") — use
  that, even over `status: kept` markers; the human in front of you outranks
  a recorded pick.
- No `kept` entries and nothing named, but the shortlist has
  `status: shortlisted` entries → `/choose` hasn't run. Show the list (score
  + reason from `meta.yaml`) and ask, once: *"Which of these should I
  develop? The rest get discarded."* (Suggest `/choose` in a fresh session
  next time if the queue is long — that's what it's for.)

Do not tailor anything the human (here or via `/choose`) has not chosen.
No keeps → nothing to develop; say so and stop after Step 2.

## Step 2 — discard the rest

Delete `queue/shortlist/<slug>/` for every role not kept — `/choose` usually
already did this, so there may be nothing to do. Discards are already in
`state/seen/` (disposition `shortlisted`), so they can never come back. No new
seen-state is written here — discarding a shortlist entry is not a new
disposition (PRD §15.7).

## Step 3 — tailor each keep

For each kept role, invoke the `tailor` subagent (opus) with the contents of
`queue/shortlist/<slug>/jd.md` and `meta.yaml`. It writes
`queue/ready/<slug>/` — `resume.yaml`, `resume.md` (via
`python3 bin/render.py resume.yaml -o resume.md`), `cover.md`, `jd.md`,
`meta.yaml` (carrying forward the triage block, `swept:`, and `fingerprint:`
from the shortlist unchanged — `seen.py audit` needs them — and setting
`status: queued`, which is what the tracker expects for a draft awaiting
Gate 2) — and
self-validates (`validate.py`, `validate.py --cover`, with `--note` where a
company note exists) and scores itself with `bin/ats_score.py` — the keyword
coverage it reports is that script's output, not its own estimate (PRD §21).
**Markdown only. No PDF** — the human makes their own file at submit time.

The tailor also researches the company on the public web for the cover's hook
(PRD §16): findings land in `profile/companies/<slug>.md` with source URLs
before they're used, the human's own lines are never edited, and LinkedIn /
Indeed / anything behind auth is off limits. Commit the note updates with the
drafts — they're provenance.

Then delete the `queue/shortlist/<slug>/` directory: the role has moved to
`queue/ready/`.

If a keep fails validation and cannot be fixed honestly, say so plainly and
show the [SHORTFALL]s — do not ship a bad draft, and do not paper over it.

## Step 4 — review it together, right now

Walk each draft exactly as `/review` would: show `resume.md` and `cover.md`,
the ATS scorecard, and the changes-made list from the tailor's report. Show the
scorecard as the tailor produced it — required tier first, every miss with its
verdict — and say plainly which misses are [SHORTFALL]s. If the human's answer
to a `[GAP]` adds evidence that covers a miss, re-run

```
python3 bin/ats_score.py --jd jd.md --variant <variant.yaml> --cover cover.md
```

after re-tailoring, and quote the new number rather than the old one.
Answer the `[GAP]`s (write answers back to `profile/evidence-bank.md` as
proper entries with tags, scope, confidence, source, narrative — then
re-tailor the affected bullet). State the `[SHORTFALL]`s plainly. Apply the
human's edits. Re-validate everything you touched:

```
python3 bin/validate.py <variant.yaml>
python3 bin/validate.py --cover cover.md --variant <variant.yaml> \
  [--note profile/companies/<slug>.md]
```

If the human asks for interview prep for a role, provide it here — likely
questions plus STAR stories built from evidence-bank narratives. Only on
request; never by default (PRD §15.6).

If the human wants to defer the walkthrough, that's fine — commit the drafts
and tell them `/review` picks it up later.

## Step 5 — commit and report

Commit `queue/` (and any evidence-bank / company-note updates) on `main` and
push (`git pull --rebase origin main` first if the push is rejected). Then
close the session with the tailor's report, one block per developed role —
angle chosen (with the proof entries it led with), the ATS scorecard (required
/ preferred / overall, misses with verdicts), changes made, [GAP]s (and their
answers if resolved live), [SHORTFALL]s, top-5 required-tier keywords used,
personalization strategy, and suggestions to strengthen. Note
the discarded roles in one line. There is no PR — the commit on `main` is the
record, and this report is the human's copy (PRD §18).

## Then hand back to the human

They submit **by hand, in their own browser**, then run `/log`. You never
submit, never navigate to a submit button, never POST to an ATS (red lines
§10).
