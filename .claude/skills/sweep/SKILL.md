---
name: sweep
description: The nightly routine entrypoint. Fetch ATS postings, triage them cheaply, and push a shortlist to main. No tailoring happens here — the human picks keeps later with /choose, then /tailor develops them. Runs unattended — no approval prompts. Never submits, never merges.
---

# /sweep — the unattended job search (PRD §4, §9, §15, §18)

You are running with **no human in the loop**. There is no one to ask. Be
precise. The red lines in `CLAUDE.md` are load-bearing here above all.

The sweep's job ends at a **shortlist**, committed straight to `main`
(PRD §18 — no sweep branch, no PR). It does not tailor. Tailoring is
expensive and human-triggered (`/choose` picks the keeps, `/tailor` develops
them, PRD §15/§18) — invoking the `tailor` subagent from a sweep is a bug.

Work on `main` the whole run; never create a branch.

**Full coverage is the default, every run.** The unattended sweep fetches
*every* board in `profile/targets.yaml` (`--source all`) and triages *every*
posting that survives fetch — no board subsetting, no pre-triage filtering by
company, role, seniority, or keyword of your own devising. Coverage is only
ever reduced by the mechanics already built into the pipeline and configured by
the human: the fetch-layer location filter, the fetch-layer `role_filter` from
`profile/goals.yaml` (opt-in, off unless they set it), the 30-day freshness
cut, seen-state dedupe, and the triage threshold. Any *other* narrowing (an
early filter to save tokens, a hand-picked subset of boards) is an
**interactive-only, explicitly-requested exception** — never the unattended
default. If a run was narrowed on request, say so in the closing report and
leave the skipped postings **un-seen**, so a later full sweep still reaches
them.

## Order of operations

0. **Pre-flight dedupe check** — `python3 bin/seen.py audit`. Confirms every
   role a prior sweep queued has a seen record; a `MISS` means the index is
   incomplete and this run would re-triage those roles. Repair first (the audit
   output names the fix), then continue. `bin/seen.py status` shows what the
   index currently holds. An empty index is normal only on the very first sweep.

1. **Fetch** — `python3 bin/fetch.py --source all` — always all sources, every
   board, never a subset. This reads
   `profile/targets.yaml`, applies the optional `role_filter` from
   `profile/goals.yaml`, skips postings last updated more than 30 days ago
   (postings with no parseable date pass through to triage), dedupes against
   `state/seen/*.jsonl`, and writes new postings to `queue/raw/`. One dead adapter logs a warning and the run
   continues — note which boards failed for the closing report, so the human
   knows coverage was partial. If fetch exits **non-zero** (every adapter
   failed), the environment is broken: **abort the sweep** and say so plainly.
   Do not report a quiet night. It also warns loudly if the seen
   index is empty. If it prints a `role_filter dropped N posting(s)` line,
   carry that number into the closing report — an opt-in narrowing the human
   configured is still a narrowing they should see the size of.

2. **Triage** — for **every** posting in `queue/raw/` (none skipped ahead of
   triage), invoke the `triage` subagent
   (haiku) once. Collect `{score, reason, red_flags}`. Sort each posting into
   one of three bands using `config.scoring`:
   - **survivor** — score ≥ `threshold`. Goes to the shortlist.
   - **near miss** — `threshold - near_miss_band` ≤ score < `threshold`. Below
     the bar, but not killed silently: a candidate for the near-miss tier
     (step 3). If `near_miss_band` is `0` or absent, this band is empty and
     triage is a hard cut, exactly as before.
   - **killed** — everything below the near-miss floor.

   **Focus, without narrowing.** Full coverage is a red line: triage *every*
   fetched posting — never skip one by title, keyword, or seniority to "save
   effort", and never subset boards (CLAUDE.md, PRD §4). A run focuses on
   shortlist-likely roles by *ordering*, not dropping: read the `titles` of
   each track in `profile/goals.yaml` (in track order — the first track is the
   human's first choice) and triage the postings whose title or department
   signals one of those tracks first, then everything else. **Derive that
   ordering from their goals file every run; never hardcode a role vocabulary
   here** — the person running this is not the person who wrote it, and a
   guessed list de-prioritises exactly the roles someone in another field
   wants. No `goals.yaml`, no ordering: triage in whatever order the postings
   come. Under a rate-limit or time pinch the likely fits get scored first;
   with no pinch the outcome is identical. The real focusing is done by a
   **sharp triage** (see `triage.md`) plus the threshold and the near-miss
   tier — not by a pre-triage filter, which would silently lose the occasional
   good role a keyword rule misjudges.

   The near-miss tier exists because a run that kills 100% of its postings
   leaves the human nothing to review and no signal *why*. Surfacing the
   closest few — with the gap that sank each one — makes a thin night or a
   mis-calibrated threshold visible instead of silent. It never lowers the
   bar for what gets tailored; that stays the human's call at Gate 1.

3. **Cap** — two independent ceilings; a near miss is never a survivor.
   - **Survivors** → `queue_cap`. If more than `config.scoring.queue_cap`
     survive, raise the threshold **for THIS RUN ONLY**. Do not write it to
     `config.yaml`. Record in the closing report what you raised it to and
     which roles it cost. (PRD §9.) The near-miss window tracks the
     *effective* threshold you used this run —
     `[effective_threshold - near_miss_band, effective_threshold)` — so raising
     the bar re-sorts borderline roles into the near-miss tier, it does not
     drop them straight to killed.
   - **Near misses** → `near_miss_cap`. Of the postings in the near-miss band,
     keep the top `config.scoring.near_miss_cap` by score; kill the rest. Near
     misses NEVER count toward `queue_cap` and NEVER auto-shortlist. Red line 9
     governs survivors; the near-miss cap is its own, smaller ceiling.

4. **Shortlist** — for each survivor **and each near miss**, write
   `queue/shortlist/<slug>/`:
   - `jd.md` — the full posting: company, title, location, apply URL, source
     ATS, and the complete JD text. This is everything `/tailor` will need;
     it must not have to re-fetch.
   - `meta.yaml` — the sweep's findings, no judgment beyond triage's:
     ```yaml
     company:
     title:
     location:
     url:
     source:            # greenhouse | lever | ashby | workable | smartrecruiters |
                        # recruitee | workday | oracle | pageup | teamtailor
     fingerprint:       # copy VERBATIM from the raw posting JSON — this is the
                        # seen-state identity; audit depends on it being exact
     status: shortlisted   # survivors; near-miss entries use `near_miss`
     swept: <YYYY-MM-DD>
     track:             # the goals.yaml track id this role serves, from
                        # triage's verdict; "none" if it serves no track
     triage:
       score:
       reason:
       red_flags: []
       miss_reason:     # near-miss entries ONLY: one line — what kept it under
                        # the bar (e.g. "wants 5+ yrs of it; the bank shows
                        # about 3"). Omit for survivors. (Named to avoid the
                        # reserved [SHORTFALL] marker, which is a permanent
                        # candidate gap — CLAUDE.md.)
     keywords: []       # top-5 ATS keywords from the JD, for the human's skim
     referral:          # matching name from connections.csv, else "none"
     company_note:      # present | missing (profile/companies/<slug>.md)
     ```
   No resume, no cover, no Opus. A shortlist entry is a *finding*, not a draft.
   Near-miss entries are the same shape as survivors — same `jd.md`, same
   `meta.yaml` — set apart only by `status: near_miss` and the `miss_reason:`
   line. They are surfaced for the human to judge, never pre-picked.

   **Zero survivors** is a valid outcome — but it is exactly when the near-miss
   tier earns its keep. If there are near misses, they are still written here
   (step 5 commits them), so the human has the closest calls to look at even on
   a night nothing cleared the bar. With zero survivors **and** zero near
   misses, skip step 5 (nothing to commit), still do step 6 for the killed
   postings (marking them on `main` is what stops tomorrow's sweep re-triaging
   them), and end by reporting "swept N, shortlisted 0, near-misses 0" with the
   threshold used.

5. **Commit the shortlist to `main` — make it durable first.**
   ```
   git add queue/shortlist/
   git commit -m "sweep: shortlist $(date +%F) · <n> candidates"
   git push origin main
   ```
   Commit `queue/shortlist/` only (`queue/raw/` is gitignored scratch;
   seen-state is its own commit in step 6). If the push is rejected
   (someone pushed to `main` meanwhile), `git pull --rebase origin main`
   and push again.

   The order is load-bearing: the shortlist must reach the remote **before**
   any posting is marked seen. A crash after this push but before step 6
   costs at worst a duplicated triage next run; the reverse order costs
   roles marked seen that were never durably queued — gone silently, forever
   (PRD §6).

6. **Seen-state — its own commit, never mixed with the shortlist.** Mark
   every terminal disposition with the CLI — do not hand-write JSONL or
   improvise inline Python:
   ```
   python3 bin/seen.py mark --disposition killed      <each killed raw .json>
   python3 bin/seen.py mark --disposition shortlisted <each surviving raw .json>
   python3 bin/seen.py mark --disposition near_miss   <each near-miss raw .json>
   python3 bin/seen.py audit --date $(date +%F)       # must print OK
   ```
   A near miss is queued to `queue/shortlist/` just like a survivor, so it gets
   a seen record too (disposition `near_miss`) — otherwise tomorrow's sweep
   re-triages it. `mark` is idempotent (already-seen fingerprints are skipped),
   so retrying is safe. The audit checks both directions: a `MISS` means a
   shortlisted/near-miss role has no seen record; a `LOST` means a
   shortlisted/near-miss seen record has no queue entry. Repair before going
   further — the output names the fix.
   Then delete the processed files from `queue/raw/` (they are recorded in
   the shard and the shortlist now), and land the shard:
   ```
   git add state/seen/ && git commit -m "sweep: seen-state $(date +%F)"
   git push origin main
   ```
   Seen-state contains no judgment and is never reviewable — it is a fact,
   not a proposal. Keeping it in its own commit keeps the shortlist commit
   readable as pure findings.

7. **Report** — end the run with a summary in the session (this is what the
   human reads in the morning; there is no PR):
   - **Shortlist** — grouped by goals.yaml track, in track order, each group
     under its track `label`. One block per shortlisted role: company, title,
     location, triage score + reason, red flags, top-5 JD keywords, referral
     match, and `[GAP] No company note for <company>` where the note is
     missing. A track with nothing this run gets one line saying so — a
     consistently empty track is the human's signal that its `titles` are off
     or its companies don't hire for it.
   - **Closest misses** — if any near-miss entries were written, a short
     section listing each: company, title, score, and the one-line `miss_reason`
     (what kept it under the bar). Say plainly these are *below* the threshold
     and surfaced only so the human can judge them at Gate 1 — the sweep is not
     recommending them. Omit the section entirely when there are none.
   - One line of headline counts: "swept N, shortlisted X, near-misses Y
     (threshold T)".
   If any adapters failed in step 1, one line naming them ("coverage was
   partial: …"). If fetch reported a `role_filter` drop count, one line naming
   it ("role_filter dropped N before triage"). If the cap raised the threshold,
   say so and name what it cost.
   Close with one line telling the human what to do next: *"Run /choose in a
   fresh session to pick keeps, then /tailor."* Nothing else. No drafts. No
   interview prep.

## Never (red lines)
- Never invoke the `tailor` subagent — tailoring is human-triggered (PRD §15).
- Never pick keeps or discard shortlist entries — that is `/choose`, Gate 1,
  and it is the human's (PRD §18).
- Never submit an application or navigate to a submit button.
- Never modify `profile/resume.yaml`, `profile/config.yaml`, or
  `profile/goals.yaml`. A sweep reads the goals; changing them is the human's.
- Never create a branch or open a PR — the sweep lands on `main` (PRD §18).
- Never fetch outside the ATS allowlist, including for company research (§4.3).
- Never exceed `queue_cap` — raise the threshold for this run and say so.

The shortlist on `main` plus the report is the deliverable: the morning's job
search, done. The human reads it over coffee, then runs `/choose` in a fresh
session (Gate 1: which of these is worth tailoring?) and `/tailor` for the
keeps.
