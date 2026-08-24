---
name: review
description: Gate 2. Run interactively in a session on main (or an /add branch). Walk each queued role's draft with the human, answer the [GAP]s (writing answers back to the evidence bank), and act on kill instructions. Never submits.
---

# /review — Gate 2, interactive (PRD §4, §8)

Run this in a session on `main` (`git pull origin main` first), or on an
`add/*` branch for a manual find. Gate 1 was the human picking keeps in
`/choose`. Gate 2 is you and the human walking the actual drafts together:
is this right?

If `queue/shortlist/` still has entries, those roles have been found but not
developed — that's `/tailor`'s job (PRD §15), and its live walkthrough usually
covers Gate 2 in the same session. `/review` is for drafts in `queue/ready/`
whose walkthrough was deferred.

## For each directory in `queue/ready/`

1. Show the draft: the tailored `resume.md`, the `cover.md`, the ATS scorecard
   (required tier first, every miss with its verdict), and the angle it argues. (Drafts created interactively via `/add`
   were already reviewed live in that session — skip them unless the human
   wants another pass.)

2. **Answer the [GAP]s.** Each [GAP] is a specific, answerable question about
   the candidate's own history ("was the Acme migration 6 or 8 months?"). Ask
   the human. When they answer:
   - Write the answer back into `profile/evidence-bank.md` as a new or enriched
     `## Evidence` entry, with `tags`, `scope`, `confidence`, `source`,
     `narrative`. Every gap filled enriches the bank permanently (PRD §3.6).
   - Re-tailor the affected bullet so the same JD never asks again.

3. **Read the [SHORTFALL]s aloud.** These are not answerable — the candidate
   just doesn't have the thing. Confirm they're stated plainly in the cover /
   not written around. Append genuinely new ones to `## Shortfalls`.

4. **Kills.** If the human says drop a role, delete `queue/ready/<slug>/`.
   The rest stay.

5. **Re-validate** anything you changed:
   `python3 bin/validate.py <variant.yaml>` and
   `python3 bin/validate.py --cover cover.md --variant <variant.yaml>`
   (add `--note profile/companies/<slug>.md` if the note exists — its numerals
   are allowed in the hook). Both must pass. The linter runs again here, not
   just in the sweep.

   Then, if an answer let you honestly cover a keyword the draft was missing,
   re-run the scorecard so the number you report is this draft's and not the
   tailor's:
   `python3 bin/ats_score.py --jd jd.md --variant <variant.yaml> --cover cover.md`

## Then hand back to the human
The human **submits by hand, in their own browser.** You never submit, never
navigate to a submit button, never POST to an ATS (red lines §10). After they
submit, they run `/log` to record it.

If a [GAP] answer or a kill is ambiguous, ask — do not guess. Questions are
cheap; assumptions are expensive (PRD principle 3.5).
