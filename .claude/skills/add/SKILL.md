---
name: add
description: Paste in a job description you found yourself (LinkedIn, a friend, anywhere). Saves it, gives a fit read, and if you say go, tailors a markdown draft and walks it with you in this same session. Never submits.
---

# /add — paste-in intake for manually found roles (PRD §14)

The human found a posting themselves. This is the interactive counterpart to
the unattended `/sweep`: because the human is sitting right here, Gate 1 and
Gate 2 collapse into this one session. The red lines in `CLAUDE.md` still hold
in full — especially: never submit, never fetch off-allowlist, never invent.

## Step 1 — get the JD text

- Pasted text: use it as-is.
- A URL on an allowlisted ATS host (Greenhouse/Lever/Ashby/Workable/
  SmartRecruiters): you may fetch it.
- Any other URL (LinkedIn, a company careers page): **do not fetch**. Ask the
  human to paste the JD text. Their own copy of a posting is their notes, which
  is allowed; you fetching it is not.

## Step 2 — save the posting

Write `profile/manual-postings/<company>-<role-slug>.md` containing: company,
title, location, closing date if stated, source ("manual — pasted by the user"),
`status: new`, and the full JD text. Add a row to the table in
`profile/manual-postings/README.md`.

## Step 3 — fit read

Invoke the `triage` subagent on the JD (score, reason, red_flags, track), then
show the human the score, the track it serves, plus any relevant
`## Shortfalls` from the evidence bank. Say what you'd tailor against and
what's missing. The threshold in `config.yaml` does **not** auto-kill here —
the human found this role and the human decides.

If triage returns `track: none`, say so plainly and neutrally — *"this doesn't
match any track in your goals.yaml; that's fine if you're widening the net, and
worth an edit to goals.yaml if you're changing direction"* — then carry on with
the same question in step 4. A role off their stated goals is their call, not a
reason to discourage them.

## Step 4 — ask: pursue, hold, or pass?

- **Hold** → set `status: hold` in the posting file, commit to `main` (it's a
  note, not a proposal), done.
- **Pass** → set `status: passed` with the human's one-line reason, commit to
  `main`, done.
- **Pursue** → continue.

## Step 5 — tailor, on a branch

- `git checkout -b add/$(date +%F)-<slug>`
- Invoke the `tailor` subagent. It writes `queue/ready/<slug>/`:
  `resume.yaml`, `resume.md` (via `python3 bin/render.py resume.yaml -o
  resume.md`), `cover.md`, `jd.md`, `meta.yaml` — and self-validates
  (`validate.py`, `validate.py --cover`, with `--note` where a company note
  exists). **Markdown only. No PDF** — the human makes their own file at
  submit time if a portal wants an upload.
- Because this session is interactive, the tailor may research the company on
  the public web for the cover's hook (PRD §16): findings go into
  `profile/companies/<slug>.md` with source URLs before use; the JD-intake
  rule above is unchanged (still never fetch LinkedIn or auth-walled pages).

## Step 6 — review it together, right now

Walk the draft exactly as `/review` would: show `resume.md`, `cover.md`, and
the ATS scorecard the tailor produced with `bin/ats_score.py` (required tier
first, every miss with its verdict), answer the `[GAP]`s (write answers back to
`profile/evidence-bank.md`), state the `[SHORTFALL]`s plainly, apply the
human's edits, re-validate everything you touched — and re-run `ats_score.py`
if an answer let you honestly cover a miss, quoting the new number. This
session **is** the review; no separate Gate 2 session needed.

## Step 7 — record

Update the posting's `status: drafted` and the README table. Commit the branch,
push, open a **draft PR** titled `Add · <company> · <role>` — one block in the
body: company, title, fit read, angle chosen and why, ATS scorecard (required /
preferred / overall), [GAP]s answered, [SHORTFALL]s.
The PR is the record and the merge vehicle, not a review queue: the human
already reviewed live.

## Then hand back to the human

They submit **by hand, in their own browser**, then run `/log` (which moves the
role to `applied/` and regenerates the tracker), then merge the PR themselves.
You never submit, never navigate to a submit button, never merge your own PR.
