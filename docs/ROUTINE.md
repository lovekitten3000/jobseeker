# The routine (paste-in) — PRD §9, §18

Create at **claude.ai/code/routines → New Routine**. Attach your private
`my-jobseeker` repo and the environment you configured in `docs/ENVIRONMENT.md`.

- **Trigger:** Scheduled → Weekdays → 06:00 local. Runs may start a few minutes
  late due to stagger; the offset is consistent.
- Minimum interval is one hour. Custom cron needs the CLI, so stick to presets —
  and "weekdays at 6am" is a preset.

> **Already have this routine from before v3.5?** The prompt below changed
> (the sweep now lands the shortlist on `main` — no branch, no PR — and the
> morning pick moved to `/choose`). **From before v3.6?** It changed again:
> triage scores against your career tracks in `profile/goals.yaml`, and the
> report is grouped by track. **From before the near-miss tier?** Once more:
> the closest below-threshold roles are queued as their own tier instead of
> being killed silently. Editing this file does **not** update the routine at
> claude.ai — open the routine and re-paste the prompt.

## Routine prompt (paste verbatim)

```
Run /sweep.

The sweep stops at a shortlist, committed to main (PRD §18). Do NOT
tailor. Do NOT invoke the tailor subagent. Do NOT pick keeps or discard
anything — the human picks via /choose later, then /tailor develops the
keeps.

Order matters (see PRD §6, §18 and the /sweep skill — the skill is
authoritative). Work on main the whole run; never create a branch:
1. bin/seen.py audit (pre-flight; repair any MISS first)
2. bin/fetch.py --source all. Non-zero exit = every adapter failed:
   abort and report, do not report a "quiet night". If it prints a
   "role_filter dropped N" line, carry N into the report.
3. Triage each queue/raw posting; keep >= config.scoring.threshold.
   Triage scores against the tracks in profile/goals.yaml (where I
   want to go), not against my last job title. Record each role's
   track in its meta.yaml. Roles scoring within
   config.scoring.near_miss_band below the threshold are NOT killed:
   the closest config.scoring.near_miss_cap of them are queued as a
   separate near-miss tier, each with the gap that sank it.
4. Write queue/shortlist/<slug>/ (jd.md + meta.yaml, copying the
   posting's fingerprint into meta.yaml verbatim) for each survivor
   (status: shortlisted) and each near miss (status: near_miss, plus
   a one-line miss_reason). Near misses never count toward queue_cap.
   Zero survivors: still write the near misses, and still mark the
   kills (step 6).
5. Commit queue/shortlist/ only ("sweep: shortlist <date> · <n>
   candidates") and push main. Nothing to commit (no survivors and no
   near misses): skip to step 6. The shortlist must be durable on the
   remote BEFORE anything is marked seen — never the other way around.
   Push rejected? git pull --rebase origin main and push again.
6. Seen-state, via the CLI (never hand-written JSONL):
   `bin/seen.py mark --disposition killed|shortlisted|near_miss
   <raw .json ...>`,
   then `bin/seen.py audit --date $(date +%F)` (must print OK).
   Delete the processed queue/raw files. Commit state/seen/ as its own
   commit ("sweep: seen-state <date>") and push main.
7. End the run with the report (this is what I read in the morning —
   there is no PR): grouped by goals.yaml track, one block per
   shortlisted role — company, title, location, triage score + reason,
   red flags, top-5 JD keywords, referral match, and a [GAP] where a
   company note is missing; then a short "closest misses" section for
   the near-miss tier, each with its score and miss_reason; a line
   naming any adapters that failed; the role_filter drop count if any;
   the raised threshold if the cap bit; and the headline counts
   ("swept N, shortlisted X, near-misses Y").
   End with: "Run /choose in a fresh session to pick keeps, then
   /tailor." Nothing else. No drafts. No interview prep.

Never:
- submit an application, or navigate to a submit button
- modify profile/resume.yaml, profile/config.yaml or profile/goals.yaml
- create a branch, open a PR, or merge anything
- pick keeps or discard shortlist entries, near misses included — that
  is the human's gate
- fetch anything outside the ATS allowlist

If more than config.scoring.queue_cap roles survive, raise the threshold
for THIS RUN ONLY, do not write it to config.yaml, and say in the report
what you raised it to and what it cost.
```

## Notes

- **Threshold is per-run.** If "raise the bar" wrote to `config.yaml`, the
  unattended routine would edit its own config nightly and ratchet away the
  threshold you calibrated in Phase 5 — and never ratchet back. Per-run,
  reported in the run's report. See the same override three mornings running?
  Then *you* change the config.

- **Limits.** Routines have daily limits (check the current number in the UI).
  One sweep a day is comfortably inside it. Rate-limit draw is shared with your
  coding work: one cheap Haiku triage call per fresh posting — a handful, once
  the backlog is behind you — and **zero** Opus runs per sweep (PRD §15). The
  expensive tailoring spend happens only when you run `/tailor` on the roles
  you chose to keep.

- **After the sweep.** The shortlist is on `main` and the run's report is the
  job search's output: scores, reasons, and keywords. Read it, then open a
  **fresh session** and run `/choose` (Gate 1: which are worth tailoring? —
  it reads only the shortlist metadata, so the pick costs almost nothing),
  then another fresh session for `/tailor`, which develops everything you
  marked kept. Discards never come back — they're already in seen-state.

- **Day one is not steady-state.** The first sweep triages your entire backlog
  (100+ postings). Run it **manually**, on a day you're not working.
