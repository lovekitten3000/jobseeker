---
name: choose
description: Gate 1. Run in a fresh session on main after a sweep. Pulls up the shortlist queue cheaply (meta.yaml only, no JDs unless asked), the human picks keeps, and the picks are committed — discards deleted, keeps marked. Then the human runs /tailor. Never tailors, never submits.
---

# /choose — Gate 1, pick the keeps (PRD §18)

The sweep ended with a shortlist on `main`. This session answers one question —
**"which of these is worth tailoring?"** — as cheaply as possible, then records
the answer in the repo so `/tailor` (a different session) can act on it without
re-asking. The repo is the database; a pick that isn't committed didn't happen.

This session is deliberately small. Do not tailor, do not research companies,
do not fetch anything. The whole point of `/choose` being its own session is
that picking keeps should not spend the context window that tailoring needs.

## Step 1 — load the queue, cheaply

```
git checkout main && git pull origin main
```

Read **only** `queue/shortlist/*/meta.yaml` — never the `jd.md` files. The
meta has everything a pick needs: triage score, reason, red flags, top-5 JD
keywords, referral match, company-note presence.

Sort the entries by their `status:` field into three groups — the sweep writes
it, and the groups are not interchangeable:

- **`status: shortlisted`** — survivors, scored at or above the threshold. The
  main pick list.
- **`status: near_miss`** — scored *below* the threshold, surfaced by the sweep
  only so a thin night isn't silent (PRD §15). Each carries a `miss_reason:`
  line — the one thing that kept it under the bar. These are **not** the
  sweep's recommendations; they exist for you to overrule the threshold if you
  want to, nothing more.
- **`status: kept`** — a prior `/choose` already picked these and `/tailor`
  hasn't run yet. List them separately as "already kept, awaiting /tailor";
  don't re-ask.

- **Empty shortlist** (no entries at all) → say "nothing to choose — the queue
  is empty" and point at `/next`. Stop.

## Step 2 — present the queue

Present the two groups **separately and labelled**, so a below-threshold role
is never mistaken for a survivor.

First, **Shortlist (met the bar)** — the `status: shortlisted` entries,
sub-grouped by their `track:` under each track's `label` from
`profile/goals.yaml`, in track order. One block per role, compact enough to
skim on a phone: company, title, location, triage score + reason, red flags,
keywords, referral match, and `[GAP] No company note` where the note is
missing. Entries with `track: none` (or written before goals existed) go last,
under "No track". If `profile/goals.yaml` is absent, skip the grouping
entirely and present one flat list.

Then, only if any exist, **Closest misses (below the bar)** — the
`status: near_miss` entries, in their own clearly-headed section. Same fields,
plus the `miss_reason:` line, and say plainly these scored *below* the
threshold and are surfaced only so you can judge them — the sweep is not
recommending them. If there are none, omit the section entirely.

Number every block across both sections so the human can answer "keep 1 and 3,
kill the rest" — a near miss is picked exactly the same way a survivor is; the
label just tells the human what they're overruling.

If the human asks for more detail on a specific role ("show me the JD for
the Torrens one"), *then* read that one `jd.md` — on request only, one at a
time. Answer questions about a role **only** from its `jd.md` and
`profile/companies/<slug>.md` if present — never from memory or priors
(red line 6). No web research here; that happens in `/tailor` (PRD §16).

## Step 3 — get the decision

Ask once, with the list in front of them: *"Which of these should I keep for
tailoring? The rest get discarded — they're already in seen-state and will
never come back."*

- Keeps and discards must together cover the queue; if the human names only
  keeps, confirm the rest are discards.
- "Discard all" is a valid outcome.
- Do not recommend, rank beyond triage's score, or nudge. The pick is the
  human's — that is what makes this a gate.

## Step 4 — commit the picks

For every **discard**: delete `queue/shortlist/<slug>/`. It is already in
`state/seen/` (disposition `shortlisted`), so it can never come back. No new
seen-state is written — discarding a shortlist entry is not a new disposition
(PRD §15.7).

For every **keep**: in `queue/shortlist/<slug>/meta.yaml`, set
`status: kept`. Touch nothing else in the file — `fingerprint:`, `swept:`,
and the triage block must survive verbatim (`seen.py audit` needs them).

Then make it durable:

```
git add queue/shortlist/
git commit -m "choose: <n> kept, <m> discarded"
git push origin main
```

If the push is rejected, `git pull --rebase origin main` and push again.

## Step 5 — hand off

Close with one line: *"<n> kept. Open a fresh session and run /tailor — it
will develop everything marked kept."* If the pick was discard-all, say the
queue is clear and point at `/next`.

## Never
- Never tailor, and never invoke the `tailor` subagent — that is `/tailor`'s
  spend, in its own session (PRD §15).
- Never submit an application or navigate to a submit button.
- Never fetch the web — no company research here (PRD §16 puts it in
  `/tailor` and `/add`).
- Never keep or discard a role the human didn't name — no picks without the
  human, no defaults, no "I went ahead and".
- Never write seen-state — discards are already seen.
- Never modify `profile/resume.yaml`, `profile/config.yaml`, or
  `profile/goals.yaml`. If a whole track keeps arriving empty or wrong, say so
  in one line at hand-off ("nothing on the *career-changer* track for three
  sweeps — its `titles` may be too narrow") and leave the edit to them. Their
  career goals are not yours to adjust.
