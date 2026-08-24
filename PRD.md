# Jobseeker — Product Requirements Document (v3)

A personal job-search pipeline. It sources roles from public ATS APIs, triages
them cheaply, tailors resumes and cover letters with provenance-checked claims,
and opens a PR a human reviews before applying **by hand**. It never
auto-submits, never scrapes, and never invents.

**How to read this.** §1–§13 are the original v3 design and are kept as
written. §14 onward amend them, in order, and a later amendment always wins:
the flow that actually runs today is §18 (the sweep lands its shortlist on
`main`; `/choose` is Gate 1; `/tailor` develops the keeps) plus §19 (roles are
scored against `profile/goals.yaml` — where you want to go — not against your
last job title), §20 (nothing in the template describes a particular career,
industry, or country) and §21 (keyword coverage is computed, not estimated;
what an *angle* is). Where §4's diagram or §6 still show a sweep branch and a
morning PR, read §18.

Every example value in this repo — in the templates, the prompts, the
docstrings, the tests — is a placeholder. The system carries no default field,
no default seniority, no default region, and no skills taxonomy; it reads all
of that from the user's own `goals.yaml`, `config.yaml`, `targets.yaml`, and
evidence bank (§19, §20).

## 1. Goals

| # | Goal | Measured by |
|---|------|-------------|
| G1 | Zero manual job searching | You never open a job board to find roles |
| G2 | Zero manual resume tailoring | You never edit a resume by hand; only approve |
| G3 | Human reviews every application before submission | 100% of submissions pass two gates |
| G4 | The tracker is never hand-edited | `tracker.csv` never appears in a hand-authored commit. A status change costs one `/log` line. ~2 min/week. |
| G5 | Reusable by anyone | Template repo → working system in < 30 min, no code edits |
| G6 | No claim about your history appears without a traceable evidence ID | `validate.py` passes on every resume variant and every cover letter. The linter catches invention; Gate 2 catches stretching. |
| G7 | Costs nothing beyond the subscription | No API key exists anywhere in the system |
| G8 | Works entirely from a browser and a phone | CLI never required, for setup or operation |

**On G4.** The invariant is intact — `tracker.csv` is still derived, and Phase
7's delete-and-regenerate test still passes byte-for-byte. What's manual is the
status field inside `meta.yaml`, and only for positive events: reply, screen,
onsite. Silence needs no input, because the ghosted timer handles it. Forgetting
`/log` entirely degrades to "ghosted," which is almost always just true. A
manual step whose failure mode is the correct default is not worth an email
integration.

**On G6.** v2 promised a property no linter can deliver. The realistic
hallucination isn't inventing a metric from thin air — it's citing `ev:0031` and
stretching what `ev:0031` says. `validate.py` is a fabrication-from-nothing
detector. It's a good one, it runs unattended, and it is not a misrepresentation
detector. That's what Gate 2 is for. Say so out loud, or you'll trust the green
check.

## 2. Non-goals

- **Auto-submission.** Never. Especially now: routines run unattended with no
  approval prompts.
- **Scraping LinkedIn/Indeed.** ToS violation, account risk, unnecessary — §4.1.
- **Company research at sweep time.** Structurally impossible (§7.1) and replaced
  by something better (§4.3).
- **Volume.** Optimizes applications-per-hour-of-your-attention. Over the cap →
  raise the threshold, never the cap.
- **Custom cron expressions.** Requires the CLI. Presets only.
- **Interview prep.** A different loop, triggered by an event that happens to
  <10% of applications. The evidence bank already holds STAR-shaped narratives
  (§8.0), so `/prep` is a natural fifth skill — but it is not part of the sweep.
- **Negotiation, networking CRM, web UI.**

## 3. Principles (invariants — violating any is a bug)

1. **The repo is the database.** Everything that must survive a session is
   committed. There is no other storage.
2. **The tracker is derived, never maintained.** Delete `tracker.csv`,
   regenerate, get an identical file.
3. **Cheap model triages, expensive model tailors.** A rate-limit argument now,
   not a cost one — the bucket is shared with your real work.
4. **Every claim traces to an evidence ID.** Enforced by a linter, not by vibes.
   Resumes and cover letters.
5. **Questions are cheap; assumptions are expensive.** The sweep writes `[GAP]`
   and moves on. It never invents.
6. **Answers get written back.** Every gap you fill enriches the bank
   permanently.
7. **The system holds no secrets.** ATS APIs are public; GitHub auth is proxied.
   Nothing to leak. Keep it that way — §10.
8. **Bookkeeping is not a decision.** Gates exist to review judgment. Never gate
   a fact. (New in v3 — see §6.)

## 4. Architecture

```
  claude.ai/code/routines
  "Nightly sweep" · weekdays 06:00 · repo: my-jobseeker
          │
          ▼
  ┌─────────────────────────────────────────────┐
  │  fresh VM · repo cloned · setup script ran  │
  │  fetch.py    ATS public APIs ──► queue/raw  │  deterministic
  │  triage      subagent, model: haiku         │  judgment, cheap
  │  tailor      subagent, model: opus          │  judgment, costly
  │  validate.py provenance gate — resume+cover │  deterministic
  │  tracker.py  applied/ ──► tracker.csv       │  derived
  │  ── state/seen/<date>.jsonl ──► main ───────┼──► fact. not gated.
  │  git commit ──► branch sweep/2026-07-17     │
  │  open PR "Sweep · 3 roles · 2 gaps"         │
  └─────────────────────────────────────────────┘
          │
          ▼
  ╔═══════════════════════════════════════╗
  ║ GATE 1 — read the PR diff (phone ok)  ║  worth applying?
  ║ close = reject all · delete a dir =   ║
  ║ reject one · merge = nothing yet      ║
  ╚═══════════════════════════════════════╝
          │
          ▼
  claude.ai/code → session ON THE SWEEP BRANCH → /review
  ╔═══════════════════════════════════════╗
  ║ GATE 2 — the draft + answer the gaps  ║  is this right?
  ╚═══════════════════════════════════════╝
          │
          ▼
  YOU submit, by hand, in your own browser
          │
          ▼
  /log → applied/ + meta.yaml → merge the PR → tracker.csv regenerated
```

### 4.1 Sourcing — public ATS APIs, not scraping

| ATS | Endpoint pattern |
|-----|------------------|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` |
| Lever | `https://api.lever.co/v0/postings/{slug}?mode=json` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{slug}` |
| Workable | `https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true` |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{slug}/postings` |

Five more adapters ship alongside these — Recruitee, Workday, Oracle
Recruiting Cloud, PageUp, Teamtailor — each reaching per-tenant hosts that
have to be allowlisted individually; `templates/targets.example.yaml` carries
the slug shapes and `docs/ENVIRONMENT.md` §1 the hosts. Which of the ten
matter to a given user is entirely a function of where they are looking, and
several fields (public sector, healthcare, education, small local employers)
are largely off all of them — that is a supported outcome, not a failure: the
system is `/add`-driven and the sweep is a bonus (§14.2, §14.5).

No auth, no anti-bot, no ToS problem — and you see roles the hour they post.
Endpoint shapes drift; each lives behind an adapter (§8.1) so a break is one
file. These domains must be in the environment allowlist (§7.1) or nothing works.

### 4.2 Referrals

Export your own connections: LinkedIn → Settings → Data Privacy → Get a copy of
your data → Connections. Commit the CSV to the private repo. Match against each
job's company. 2nd-degree isn't exportable and getting it means scraping — don't.

### 4.3 Company notes — research, inverted

The cover letter needs a specific hook, and generic praise is worse than none.
The tailor can't read the company's website: the allowlist is five ATS hosts
(§7.1), and Full network access on the one unattended loop trades the whole
structural guarantee for a paragraph of marketing copy.

So invert it. When you add a company to `targets.yaml`, write three lines about
it in `profile/companies/<slug>.md`. This is better than scraped research: it's
yours (authentic), specific (you only write it for companies you want), it can't
hallucinate (your own prose quoted back), and it can't break (no fetch). It's
also a filter — if you can't write three honest lines about why you'd go, the
company doesn't belong in `targets.yaml`.

Optional. No note → the cover opens on the role. The sweep nudges you: a company
that cleared triage with no note fires `[GAP] No company note for Acme`.

## 5. Repo structure — two repos

### 5.1 `jobseeker-template` — public template repo

Code, skills, agents, templates, docs. Zero personal data, ever. Marked as a
GitHub template repository. (This repo.)

### 5.2 `my-jobseeker` — your private repo

Created via **Use this template → Private**. Your data lives here and is
committed, because in a cloud session committed is the only kind of existing.
`profile/` (evidence-bank, resume.yaml, voice.md, connections.csv,
companies/, config.yaml, targets.yaml), `state/seen/`, `queue/ready/`,
`applied/`, `tracker.csv`.

Private is the whole security model. No gitignore protects you — the sandbox
needs these files. What protects you is that the repo is private and the sandbox
is disposable. Pull template updates later with `git remote add upstream` + merge.

## 6. State and branch model ← the v2 fix

v2 committed two artifacts in one commit and gated both behind one merge.

| | `state/seen/` | `queue/ready/` |
|---|---|---|
| What it is | fetch-layer bookkeeping | a proposal |
| Contains judgment? | no | entirely |
| Reviewable? | nothing to review | that's the point |
| Correct lifecycle | monotonic, append-only, forever | becomes `applied/`, or dies |

**Rule: seen-state is written to `main` on every run and never appears in a PR.**
Closing a PR (the correct action when no role is good) must not destroy the
record that you saw those roles. This is principle 3.8.

- **Sharded, not one file.** `state/seen/<date>.jsonl`, one append-only file per
  sweep. Two runs adding two files can never conflict.
- **Written last, not first.** A posting is marked seen only when it reaches a
  terminal disposition — killed by triage, or landed in `queue/ready/`. Mark at
  fetch and crash at tailor, and those postings are seen, never queued, gone
  silently.

**Consequence:** the sweep branch is the application workspace. Created → PR
(Gate 1) → session on that branch → `/review` (Gate 2) → you submit by hand →
`/log` writes `applied/` → merge. `main` holds `profile/`, `state/`, `applied/`,
`tracker.csv`. Branches hold in-flight work.

## 7. Cloud environment configuration

Configured once, in the web UI, at the environment selector. No CLI. See
`docs/ENVIRONMENT.md` for the paste-in allowlist and setup script.

### 7.1 Network access

Default **Trusted** includes no ATS host. Select **Custom**, include the package
managers (for PyPI), and add the five ATS hosts plus `jobs.ashbyhq.com`. Avoid
**Full** — a tight allowlist is a structural guarantee an unattended agent can't
POST your data somewhere unexpected. This kills sweep-time company research, and
that trade is worth it (§4.3).

### 7.2 Setup script

Runs as root on Ubuntu 24.04 before Claude starts. `pip install
--break-system-packages typst pyyaml httpx pydantic` then import-check. **No
`|| true`** — it swallows a failed Typst install and gives you a 6am PR with no
PDFs and no error. The Typst gotcha: install from **PyPI**, not the GitHub
release binary (which 403s under the proxy).

### 7.3 No secrets

Nothing to store. ATS APIs are public; GitHub auth is proxied outside the
sandbox. A system that needs no secrets can't leak them.

## 8. Module contracts

### 8.0 `profile/evidence-bank.md` — the master resume

The master-resume prompt's output, given IDs and a schema. Exhaustive by design.
Nothing is ever deleted — obsolete entries get `status: retired`. Not for
submission. Every phase is capped by this file.

`confidence` is the load-bearing field:

| Prompt said | Field | validate.py |
|---|---|---|
| a number you gave, with a source | `measured` | may appear as a hard metric |
| `~40% (my estimate, unverified)` | `estimated` | hard metric → FAIL. May be phrased directionally. |
| `[METRIC UNKNOWN — impact was: …]` | `qualitative` | any numeral → FAIL |

No Skills Inventory section (derivable from tags). No Change Log (`git log`).

### 8.1 `bin/fetch.py`

`fetch.py [--source ats|all] [--dry-run]`. Reads `targets.yaml` →
`lib/sources/<ats>.py`, each `fetch(slug) -> list[Posting]`. Dedupes on
`sha256(company + normalized_title + location)` against the union of
`state/seen/*.jsonl`. ≤1 req/sec/host, identifying UA, backoff. One broken
adapter logs a warning; the sweep continues. Never calls a model. Never writes
seen-state — that's `lib/seen.py`, at terminal disposition only.

### 8.2 `bin/render.py`

`render.py <resume.yaml> -o <out.pdf>`. Typst via the `typst` package.
ATS-parseable output: real text, single column, no tables/columns/graphics/text
boxes/icons, standard headings. Fails loudly if any bullet lacks `ev`. If the PDF
isn't one you'd send unedited, fix it here or the system dies.

### 8.3 `bin/validate.py` — the important one

`validate.py <variant.yaml> [--bank …] [--resume …]` and
`validate.py --cover <cover.md> --variant <variant.yaml>`.

Resume mode fails if: a bullet has no `ev`; an `ev` doesn't exist in the bank; a
hard metric traces to `confidence: estimated`; any numeral traces to
`confidence: qualitative`; company/title/dates diverge from canonical
`resume.yaml`; or a technology appears that no evidence entry tags.

Cover mode (new in v3) fails if a numeral, employer name, or technology appears
in `cover.md` that does not appear in the already-validated `variant.yaml`.
(Numerals in the company note — the hook — are also allowed via `--note`.)

Deterministic, regex-able, no model in the gate. Transitively sound: the variant
already passed provenance, so the cover can only re-assert traced facts. It does
**not** constrain motivation, opinion, why-this-role, or voice — those aren't
claims about your history. **It catches invention. It does not catch stretching**
(G6). That's Gate 2.

### 8.4 `bin/tracker.py`

Scans `applied/*/meta.yaml` + `queue/ready/*/meta.yaml` → `tracker.csv`. Derived
columns: `days_since_applied`, `status` (auto-ghosted after `ghost_days` silent
days), `next_action`, `funnel_stage`. No Google Sheets — GitHub renders committed
CSVs as a sortable table on desktop and mobile.

### 8.5 Claude assets

Cloud sessions pick up `.claude/agents/`, `.claude/skills/`, and `CLAUDE.md` from
the clone automatically.

- **`triage.md`** — model: haiku; tools Read, Grep, Glob. One posting per
  invocation. Writes nothing. Strict JSON `{score, reason, red_flags}`. Reads
  `config.yaml` constraints and the bank's `## Shortfalls`. **triage's score is
  the only score** — the tailor reports coverage instead.
- **`tailor.md`** — model: opus. Survivors only. Must run `validate.py` and
  `validate.py --cover` on its own output before finishing. Reports chosen angle,
  coverage, changes.

**The two gap types.** `[GAP]` = you don't know something about the candidate
(answerable; written back to `## Evidence`). `[SHORTFALL]` = the candidate lacks
something the role wants (not answerable; appends to `## Shortfalls`). Both appear
in the PR body; only `[GAP]` has a loop.

### 8.6 Cover letter contract

Length: `config.cover.max_words` (behavioural → config, not a constant).
Default 250 as first written; raised to 450 in §15.5 once tailoring became
interactive, which is what `templates/config.example.yaml` ships. Structure: specific hook → why-this-candidate with supported metrics →
one strength by example → confident close with a CTA. The hook comes from the
company note or the JD, never the web. Banned: "I am writing to apply", "excited
to apply", restating the resume, generic praise, buzzword stacking, first person
in resume bullets. Matches `voice.md`. Passes `validate.py --cover`.

The prompt's trailing sections (personalization strategy, top-5 keywords, three
suggestions) are PR-body blocks, not files.

## 9. The routine

Create at `claude.ai/code/routines`. Weekdays, 06:00 local. Preset only (custom
cron needs the CLI). The paste-in prompt lives in `docs/ROUTINE.md`. **Threshold
is per-run** — raising the bar never writes to `config.yaml`, or an unattended
routine ratchets away your calibrated threshold nightly and never ratchets back.
Day one triages your whole backlog (100+ postings); run it manually.

## 10. `CLAUDE.md` red lines

The sweep runs with no human in the loop and no approval prompts. See `CLAUDE.md`
for the full, load-bearing list: never fabricate; never present an estimate as
fact; never submit; never scrape; never fetch off-allowlist; never assert an
unbacked company fact; never write `resume.yaml`/`config.yaml` during a sweep;
never put seen-state in a PR; never exceed `queue_cap`; never merge your own PR;
never delete from the bank; `[GAP]` not a guess; `[SHORTFALL]` stated plainly.

## 11. Build phases

Each passes before the next. Phase 0 is the one-shot.

- **Phase 0 — Scaffold.** Everything in §5.1. Adapters for Greenhouse, Lever,
  Ashby minimum. Accept: `fetch.py --dry-run` clean; `validate.py` passes a good
  fixture and fails one with a missing `ev`; `validate.py --cover` fails a letter
  with a number absent from its variant; zero real people/companies; marked as a
  template repo.
- **Phase 1 — Instance + environment.** Accept: a web session can
  `curl …/boards/stripe/jobs` and `python -c "import typst"`.
- **Phase 2 — Evidence bank.** `/setup`. Accept: 40+ entries, all with tags,
  scope, confidence, narrative; every measured has a source; 3+ angles;
  `## Shortfalls` non-empty.
- **Phase 3 — Render.** Accept: a PDF you'd send unedited; text parses cleanly.
- **Phase 4 — Sourcing.** Accept: 100+ deduped JDs, zero model involvement; the
  persistence test (re-run → zero new); the close-PR test (still zero).
- **Phase 5 — Triage calibration.** Accept: agree with ~90% of kills on 50
  postings.
- **Phase 6 — Tailor + gap loop.** Accept: 3 end-to-end drafts pass both
  validators; a `[GAP]` fires, is answered, lands in the bank, doesn't re-ask; a
  `[SHORTFALL]` is stated plainly. Then try to make the tailor stretch an `ev` —
  it'll pass the linter. That's G6's boundary.
- **Phase 7 — Tracker.** Accept: delete + regenerate → identical; backdate past
  `ghost_days` → row flips to ghosted; renders on GitHub mobile.
- **Phase 8 — Routine.** Accept: a week unattended; a PR each morning; queue
  never exceeds cap; a dead adapter doesn't kill the run; nothing submitted.

## 12. Reusability (G5)

Template repo → private instance. No fork, no clone, no local git.
`docs/ENVIRONMENT.md` and `docs/ROUTINE.md` have the paste-ins. `/setup` is the
whole onboarding. Everything behavioural lives in `config.yaml`. Adapters are one
file per ATS.

## 13. Definition of done

06:04, a PR appears. Over coffee, on your phone, you read three roles you'd
genuinely take — each with a score you trust, a tailored resume, a letter you'd
send, a referral path where one exists, an honest note about what they want that
you haven't got, and a sharp question or two about your own history. You open a
session on the branch, answer them, and submit by hand. The roles you didn't
want, you closed — and they never came back. You never searched for a job. You
never tailored a resume. You never paid for an API call. You approved every word
that went out under your name.

## 14. Amendments (v3.1 — 2026-07-17, workflow smoothing)

Requested by the user after first real use. Everything in §1–§13 stands except
where amended here.

1. **Markdown is the deliverable; PDF is the human's problem.** The tailor
   produces `resume.md` (via `render.py`, which now renders markdown by
   default) alongside the validated `resume.yaml`. No PDF is rendered anywhere
   in the pipeline — the human converts to a file themselves at submit time if
   a portal demands an upload. Rationale: markdown is reviewable on a phone,
   diffable in a PR, and the user explicitly does not want PDFs generated.
   §8.2's ATS-parseability rules (single column, standard headings, real text)
   still govern both output modes.

2. **`/add` — manual intake is first-class.** Most of the user's real roles
   are found by hand on sites the sweep can't reach (custom career pages,
   LinkedIn). `/add` takes a pasted JD, saves it to
   `profile/manual-postings/`, gives a triage fit read, and, if the human says
   pursue, tailors and reviews the draft in that same session. Because the
   human is present, Gate 1 and Gate 2 collapse into the live session; the
   draft PR remains as the record and the merge vehicle. All red lines hold:
   paste-only for off-allowlist sources (never fetch), never submit, never
   merge your own PR.

3. **`/next` — the routine is self-describing.** A read-only skill that
   answers "what do I do now?" from repo state. Fixes the post-setup dead end.

4. **The style gate.** `validate.py` now also fails banned style patterns in
   resume bullets and covers: em dashes, AI-speak vocabulary (delve, leverage,
   tapestry, unlock…), fake reveals ("here's the truth", "at the end of the
   day"), filler openings/closings, the negation-parallel family ("not just
   X…"), and, via regex, the "It's not X, it's Y" structure. Driven by
   `config.yaml` → `style.banned` and `style.banned_regex`, with built-in
   defaults. Same boundary as ever: deterministic, no model in the gate. It
   catches the tells; the judgment-only rules (neat trios, statement-then-echo,
   sentence burstiness) live in `voice.md`, and the tailor must self-review
   against that checklist before validating. Gate 2 (or the live `/add`
   review) still owns stretching.

5. **The sweep is dormant until `targets.yaml` has companies.** Nothing about
   §4/§9 changes; the steady-state routine is simply `/add`-driven until the
   user adds careers-page URLs. `/next` says so out loud.

**The smoothed routine, in one line:** paste a JD into `/add` (or let the sweep
find one) → review the markdown draft → submit by hand → `/log` → merge. Lost?
Run `/next`.

## 15. Amendments (v3.2 — 2026-07-17, the shortlist gate)

Requested by the user after reading the first sweep-produced drafts. Two
problems, one structural fix.

**The problems.** (a) `resume.md` and `cover.md` quality out of the unattended
tailor was not good enough to send. (b) Token burn: the sweep ran an Opus
tailoring pass for *every* survivor, including roles the human then rejected at
Gate 1 — the most expensive step in the pipeline was spending itself on roles
that never got applied to.

**The fix: split the sweep at a new gate.** Tailoring moves out of the
unattended run entirely and becomes human-triggered.

1. **The sweep stops at a shortlist.** After triage, cap, and seen-state, each
   survivor is saved to `queue/shortlist/<slug>/` — `jd.md` (the full posting)
   plus `meta.yaml` (triage score, reason, red flags, top JD keywords, referral
   match, company-note presence). The branch + draft PR now carries the
   shortlist, not drafts. The unattended run invokes **zero** Opus tailoring;
   steady-state cost is ~11 Haiku triage calls.

2. **Gate 1 is now the job-search gate.** The morning PR answers "which of
   these is worth tailoring?" — a cheaper question than "is this draft right?".
   The human reads the shortlist and picks keeps. Close the PR = reject all
   (seen-state on `main` guarantees nothing comes back).

3. **`/tailor` — resume and cover development, on demand.** Run in a session on
   the sweep branch. The human names the keeps; discarded shortlist entries are
   deleted (they stay seen). For each keep, the `tailor` subagent produces
   `queue/ready/<slug>/` exactly as before, and — because the human is present —
   the Gate 2 walkthrough happens live in the same session, `/add`-style.
   `/review` remains for drafts the human defers.

4. **The tailoring craft spec is upgraded.** `tailor.md` now embeds the full
   resume-writer and cover-letter method the user supplied (JD analysis → bank
   mapping → ATS keyword alignment → summary/bullet/skills rules → structured
   cover). Two adaptations keep it inside the red lines: "research the company"
   draws **only** from the JD and `profile/companies/<slug>.md` (§4.3 stands),
   and the "ATS match score" is reported as *keyword coverage* (n of m JD
   keywords covered, with the missing ones listed) — triage's score remains the
   only fit score (§8.5).

5. **Cover length.** Target 300–450 words; `config.cover.max_words` raised to
   450. §8.6's structure and bans stand.

6. **Interview prep** stays out of every unattended path (§2 holds). In an
   interactive `/tailor` or `/review` session the human may ask for it and get
   likely questions plus STAR stories built from evidence-bank narratives.

7. **Seen-state disposition** gains a value: `shortlisted` (terminal at sweep
   time, alongside `killed`). A shortlist entry later discarded at `/tailor`
   needs no new record — it was already seen.

**The routine, restated in one line:** the sweep searches and shortlists → you
pick keeps from the PR → `/tailor` develops the resume and cover for the keeps
only → you submit by hand → `/log` → merge.

## 16. Amendments (v3.3 — 2026-07-17, researched covers)

Requested immediately after v3.2: with tailoring now interactive, the user
wants Opus to research the target company for the cover letter, not just quote
the JD and a hand-written note back.

**Why this is safe now when §4.3 said it wasn't.** §4.3's ban was aimed at the
*unattended* loop: an agent nobody is watching, with open network access,
asserting company facts is exactly the hallucination and exfiltration surface
the allowlist exists to close. Tailoring no longer runs in that loop (§15). In
a `/tailor` or `/add` session the human is present and every draft is walked
through live before anything ships.

1. **Research flows through the note.** The tailor may research the company on
   the public web — official site, newsroom, docs, reputable press — and MUST
   write what it found into `profile/companies/<slug>.md` (a
   `## Researched <YYYY-MM-DD>` section, one source URL per fact) **before**
   using any of it. The human's own lines are never edited. The cover then
   draws from the JD and the note, exactly as before, and
   `validate.py --cover --note` already admits note numerals — the note is now
   also the research provenance record. Red line 6 is unchanged in substance:
   no company fact from memory, no company fact without a written source.

2. **What research never touches.** LinkedIn, Indeed, anything behind auth —
   red line 4 stands, no exceptions. And nothing changes for the unattended
   sweep: its environment allowlist stays exactly §7.1, and it still never
   researches, because it never tailors.

3. **Hand-written notes still win.** Research supplements §4.3; it does not
   replace it. The human's three honest lines about why they'd go remain the
   strongest hook material; the tailor leads with them when present and uses
   research to sharpen, not to substitute.

4. **Unverifiable means unusable.** A company claim the tailor cannot pin to a
   fetched page goes nowhere — not in the note, not in the letter. Generic
   praise is still banned (§8.6); research exists to make the hook *specific*,
   and a specific hook that might be wrong is worse than a plain opening on
   the role.

## 17. Amendments (v3.4 — 2026-07-17, sweep hardening)

A review of the sweep's failure modes found ways an unattended run could lose
roles or lie by omission. All fixes make the existing §6 principles hold under
crashes; none changes a gate or a red line.

1. **Durable-before-seen ordering.** The sweep commits and pushes
   `queue/shortlist/` on the sweep branch *before* marking anything seen, and
   only then writes the shard to `main`. §6's "written last" said mark-at-fetch
   loses postings; the same argument applies between marking and queueing. A
   crash now costs at worst a duplicated triage next run — never a role that
   was seen but never queued.

2. **Fingerprints travel with the posting.** `fetch.py` embeds the full
   fingerprint in each raw JSON; the sweep copies it verbatim into shortlist
   `meta.yaml`; `/tailor` carries it into `queue/ready/`. `seen.py` prefers
   the stored fingerprint over recomputing from meta text, so a prettified
   company name (the two-word display name vs the board's own squashed slug)
   can no longer produce a false audit MISS. `seen.py mark`/`check` also accept a queue
   `meta.yaml` or directory, so a missing seen record is repairable after the
   raw files are gone.

3. **The audit checks both directions.** `seen.py audit --date <shard>`
   additionally verifies every `shortlisted` row in that day's shard still has
   a `queue/` or `applied/` entry (`LOST` otherwise). The sweep runs it before
   opening the PR.

4. **A broken environment fails loudly.** `fetch.py` exits non-zero when every
   adapter failed, and the sweep aborts instead of opening a PR that reads as
   a quiet night. Partial adapter failures are named in the PR body.

5. **Zero survivors → no PR.** The kills are still marked on `main` (that is
   what keeps them from coming back); an empty PR is noise, not a gate.

6. **`queue/raw/` is gitignored scratch.** Seen shards and the shortlist are
   the durable records; raw fetch JSON can never leak into a PR, and an
   interrupted sweep's leftovers are simply re-fetched (§6 stands).

7. **Tool permissions match the split pipeline.** `bin/seen.py` joined the
   allowlist (it runs unattended). The blanket `WebFetch` deny predates §16
   and silently broke interactive company research; it is removed. What keeps
   the *sweep* off the open web is, as §7.1 always said, the environment
   allowlist — the structural guarantee — plus red line 5, not a tool flag
   shared by both environments.

## 18. Amendments (v3.5 — 2026-07-17, main-line shortlist + /choose)

Requested by the user. Two changes, one motive: the morning pick should cost
almost nothing — not a branch checkout, not a PR read stapled to a session
that then has to carry the whole shortlist in context into tailoring.

**The changes.**

1. **The sweep lands on `main`.** No sweep branch, no morning PR. The sweep
   commits `queue/shortlist/` directly to `main` (its own commit, pure
   findings), then the seen shard (its own commit, pure bookkeeping), and ends
   with the shortlist report as the run's chat output — the same per-role
   blocks the PR body used to carry. §17.1's ordering survives intact: the
   shortlist commit must reach the remote *before* anything is marked seen.

2. **Gate 1 moves from the PR to `/choose`.** A deliberately tiny interactive
   session on `main`: it reads *only* `queue/shortlist/*/meta.yaml` (never the
   JDs, except one at a time on request), presents the queue, and records the
   human's picks — discards deleted (already seen; §15.7 stands, no new
   disposition), keeps marked `status: kept` in `meta.yaml` — then commits and
   pushes. The pick is durable repo state (§3.1), so `/tailor` runs in a
   *fresh* session with a clean context window and never re-asks.

3. **`/tailor` develops what's kept, on `main`.** Keeps = shortlist entries
   with `status: kept` (a human naming roles in the prompt still outranks the
   marker; with neither, it falls back to asking, as before). Drafts commit to
   `main`; the closing report replaces the PR-body update. `/log`'s "merge the
   PR" step applies only to `/add`'s branches now — sweep-path roles have no
   PR, so the commit is the record.

**What this trades away, deliberately.** The PR was a reject-all affordance
(close it) and a review surface. Both move into `/choose`: "discard all" is an
explicit, valid pick, and the queue presentation *is* the review surface. A
bad sweep's shortlist now sits on `main` until `/choose` clears it — accepted:
the shortlist is a finding, not a claim, and seen-state was already on `main`.

**What does not change.** Every red line holds. Gate 1 is still a human gate —
the sweep and `/tailor` are both forbidden from picking; a gate you can open
yourself still isn't a gate, and `/choose` refuses to recommend. Red line 10
(never merge your own PR) still governs `/add`'s PRs and any other PR. §6's
seen-state rules, §15's shortlist split, and §17's hardening all stand;
`seen.py audit --date` runs during the sweep, before `/choose` can delete
anything, so the LOST check is unaffected.

**Migration note.** The routine prompt at claude.ai is a paste — editing
`docs/ROUTINE.md` does not update it. Re-paste after adopting v3.5. An
in-flight `sweep/<date>` branch from before v3.5 finishes under the old flow
(pick from its PR, `/tailor` on the branch, merge); the new flow starts with
the next sweep.

**The routine, restated in one line:** the sweep searches, shortlists, and
pushes to `main` → `/choose` (fresh session, cheap) is where you pick keeps →
`/tailor` (fresh session) develops the keeps only → you submit by hand →
`/log` → done, no merge.

## 19. Amendments (v3.6 — 2026-08-01, career goals + shareability)

The trigger: this repo gets handed to friends, and a friend is not a clone of
its author. Two defects surfaced, one cosmetic and one structural.

### 19.1 The structural defect — the system modelled history, never intent

`profile/` held the evidence bank (where you have been), `resume.yaml` (where
you have been, canonically), `voice.md` (how you write), `config.yaml`
(constraints), and `targets.yaml` (which companies). Nothing anywhere said
**what job you want**.

So triage's only positive fit signal was `## Angles` — positioning stances
derived from past work. Fit meant *resemblance to your last job*. For someone
who wants more of the same, that is a decent proxy and the defect is invisible.
For everyone else it inverts the product:

- A **career changer** gets every role they want scored below threshold and
  killed, and gets shortlisted for the career they are trying to leave.
- A **graduate** is scored against three internships and a thesis, with no way
  to say which of five directions they are actually chasing.
- Someone **open to two directions** has no way to express both, so the weaker
  one silently never appears.
- Anyone whose target companies post across many functions burns a triage call
  on every warehouse and sales role at those companies, scored on the wrong
  axis.

**The fix: `profile/goals.yaml`** (`templates/goals.example.yaml`), a first-
class profile artifact holding one to three ordered **tracks**. Each track:
`id`, `label`, `titles`, `seniority`, `why`, `pivot`, `supporting_angles`,
`must_have`, `avoid` — and, when `pivot: true`, the two fields that make a
career change work honestly: `transferable` (which evidence carries across, in
the candidate's own words) and `known_gaps` (what they plainly lack).

Wiring:

- **`triage`** scores against the tracks *first*, then asks whether the
  evidence supports the role. A posting serving no track is off-target however
  well the history fits it. On a pivot track, missing domain title/years is
  friction rather than a kill, `transferable` counts as real support, and
  `known_gaps` are pre-declared rather than discovered. The verdict gains a
  `track` field, which flows into `meta.yaml` and through to `/choose`.
- **`/setup`** interviews for goals *before* the evidence bank — the goal
  decides which evidence is worth digging for, which matters most on a pivot,
  where the relevant material is buried under an unrelated job title.
- **`/sweep`** derives its triage *ordering* from the tracks' `titles` instead
  of a hardcoded role vocabulary, and groups the report by track.
- **`/tailor`** inverts its default ordering on a pivot track: lead with the
  transferable evidence, keep the rest of the history present and honest but
  shorter. Never hide a job, never re-label one, never claim the domain
  experience that isn't there.
- **`/choose`** groups the shortlist by track; **`/next`** treats a missing
  `goals.yaml` as the top action and reports tracks that never yield.

**Optional `role_filter`** (in `goals.yaml`, off by default) filters postings by
title at fetch time, the same class of bookkeeping as `location_filter`. It is
opt-in because it is the one narrowing that can drop a role triage would have
kept; `fetch.py` prints the drop count and the sweep reports it, every run.
`--ignore-role-filter` forces full coverage.

**What does not change.** Every red line holds. Goals inform judgment; they
never license invention. A pivot is made credible by real adjacent evidence
plus a plainly stated `[SHORTFALL]`, never by blur — and `validate.py` still
fails a title that diverges from `resume.yaml`. Nothing may write
`profile/goals.yaml` during a sweep (red line 7); a track that keeps coming up
empty is *reported* to the human, never quietly retuned. Their career goals are
theirs.

### 19.2 The cosmetic defect — the template was one person's instance

The product was named for its author in `README.md`, `PRD.md`, `CLAUDE.md`,
`pyproject.toml`, and the outbound HTTP User-Agent; a third person's name was
baked into a `meta.yaml` example; `/sweep` hardcoded one candidate's target
role vocabulary; `triage` anchored its level examples to it; and `tailor`
assumed software engineering throughout — Azure DevOps as the model bullet,
"Programming Languages / Cloud Platforms / CI/CD" as the skills taxonomy,
`technologies:` as the name of the skills field. A nurse, teacher, or
electrician using this got a system that was visibly not built for them, and a
sweep that de-prioritised exactly their own roles.

Fixed: the product is **Jobseeker**, attribution stays in `README.md` and
`LICENSE`; prompts carry examples from several fields; the skills field accepts
`skills:` as a synonym for `technologies:` (both keys still validate and
render); `/setup` scales the evidence-bank target to career stage and states
that `confidence: qualitative` is first-class, because plenty of real work is
judged by outcome rather than metric.

Also added for shareability: `LICENSE` (MIT), a CI workflow running the
acceptance tests, and `bin/check_template_clean.py` — a guard that fails if
personal data is ever committed to the shared template. The guard runs in CI
only on the template repo itself, so a friend's private instance, whose
`profile/` is *supposed* to be full, never sees it fail.

## 20. Amendments (v3.7 — 2026-08-19, no defaults, no identifiers)

§19.2 fixed the parts of the template that named its author or assumed her
industry. A second pass found the same defect one layer down, in the values
nobody thinks of as content: the *examples*. They were all from one career, in
one country.

**What was still specific.** `goals.example.yaml` shipped a filled-in "data
analyst" track — a real label, real title keywords, a real seniority — so the
file read as a starting point rather than a form, and the first user to keep a
line of it would be scored against a career they never named.
`targets.example.yaml` and the test suite encoded one region's cities, states,
and country codes as the worked example of a `location_filter`.
`config.example.yaml`'s constraint comments assumed a salary band and a
tech-industry idea of a dealbreaker. Four adapters described their behaviour in
terms of that same region ("scoping to AU", "nothing AU is lost"), and one
printed it at runtime. The `tailor` prompt's casing examples named one
country's certifications and another's school curriculum. None of this was
wrong for its author; all of it was noise, or worse a nudge, for anyone else.

**The rule, stated once.** *The template defines nothing about the person using
it.* Not a field, not a seniority, not a region, not a currency, not a skills
taxonomy, not a job title. Every value in an example file is an angle-bracketed
placeholder that a human replaces; every worked example in a prompt either
spans several unrelated fields or names none. Where a real name survives — a
board slug in an adapter docstring, the smoke-test `curl` in
`docs/ENVIRONMENT.md` — it is there because it documents the *shape of an
external API* and a user needs something they can paste and verify, never
because it is a recommendation. Attribution stays where attribution belongs:
`LICENSE`.

**Where the specifics went instead.** Nowhere — they are the user's to supply.
`goals.yaml` holds the titles and the seniority, `config.yaml` the constraints
and the currency, `targets.yaml` the companies and the locations, the evidence
bank the skills vocabulary. Every one of those is read at runtime and edited
only by the human (red line 7). A test needing a place name uses an invented
one, so no region reads as the default.

**What does not change.** No behaviour, no gate, no red line: this pass moved
example values and comments, plus one log line and one error message that
mentioned a region. `bin/check_template_clean.py` still guards the other half
of the same promise — that no *person's* data reaches the shared template — and
CI still runs it on the template repo only.

## 21. Amendments (v3.8 — 2026-08-20, the scorecard and the angle)

Two things the pipeline talked about constantly and defined nowhere: the ATS
keyword coverage the tailor reported, and the *angle* every stage referred to.

### 21.1 Coverage was a number the model made up

§15.4 told the tailor to report "keyword coverage, n of m, with the missing
ones listed" and left it there. So the model extracted the keywords, decided
which ones its own draft covered, and graded itself — a number that drifts with
the draft's confidence rather than its content, in the one place the product
promises a mechanical check.

**The fix: `bin/ats_score.py`.** Deterministic, no model in it, same JD and
same draft in, same number out. It reads the posting, ranks the posting's *own*
repeated terms (weighting a requirements block above the culture paragraph),
tiers them `required` / `preferred` / `body`, and reports which appear in the
variant and the cover. Matching is tolerant where tolerance is honest —
`ci/cd` finds `CI-CD`, a plural finds its singular, `optimisation` finds
`optimization` — because which spelling a posting uses says nothing about
whether the candidate did the work.

Wiring: the `tailor` subagent runs it as soon as a draft exists and again after
every change, writes a scorecard (every keyword, its tier, a verdict:
covered / claimable / **[SHORTFALL]**), and reports *the script's* numbers.
`/tailor`, `/add`, and `/review` show that scorecard and re-run the script when
a Gate 2 answer lets a miss be covered honestly.

**What it is not.** Not a fit score — triage's is still the only one (§8.5).
Not a target: there is no floor, deliberately, because a floor is an
instruction to reach a number and this system's whole point is that a draft
stops where the evidence stops. A draft at 12 of 20 with every miss honestly a
[SHORTFALL] is finished; a draft at 19 of 20 with one stretched bullet is the
failure G6 warns about. Coverage rises two honest ways — surfacing evidence
that was buried, and using the posting's word for work an entry plainly
describes — and no third way. The script also flags a term repeated past
`ats.max_repeats`, because stuffing loses the human reader the parser won.

Field-neutral by construction (§20): no skills list, no role vocabulary, no
industry taxonomy. It knows English function words and hiring-document
boilerplate; everything else it learns from the posting in front of it, and
every cue list is overridable under `ats:` in `config.yaml`.

### 21.2 "Angle" was load-bearing and undefined

`## Angles` was triage's positive support signal, the thing `/tailor` chose and
reported, and the target of every track's `supporting_angles`. Its definition
was five words in `/setup`: "derive 3+ angles (positioning stances)". The
format was a free bullet list, nothing linked an angle to the evidence behind
it, and nothing checked that an angle a variant claimed existed at all.

**The definition, stated once.** An angle is a **positioning stance: one claim
about what the candidate is *for*, proved by at least two evidence entries,
aimed at a track.** Three things sit side by side and are not interchangeable:

| | holds | answers |
|---|---|---|
| `goals.yaml` track | titles, seniority, pivot | what am I applying FOR |
| `evidence-bank.md` entries | what happened, with `confidence` | what have I DONE |
| `evidence-bank.md` `## Angles` | claim, proof, serves | what is the ARGUMENT |

**The format**, in the bank (`templates/angle-entry.md`):

```
### angle: <slug>
claim:  one line, the candidate's own words
proof:  ev:0031, ev:0044
serves: <track ids from goals.yaml>
```

The original one-bullet shape still parses, so a bank written before this
amendment keeps working; `--lint-bank` reports it as unproven rather than
breaking it.

**Enforcement, at the linter's usual boundary.** `validate.py --lint-bank`
fails an angle with no claim, an angle fewer than two entries support ("an
angle nothing proves is a slogan"), an angle citing an `ev:` that isn't in the
bank, and an entry citing an angle the bank never declared. Resume mode fails a
variant positioned on an angle the bank doesn't hold — the positioning is
provenance like everything else. What it still cannot judge is whether an angle
is a *good* pitch; `/setup` asks the human that out loud.

**The angle now changes the draft.** It used to be a label in a report. The
`tailor` prompt makes the choice do three things or it wasn't a choice: the
summary opens on the angle's claim made concrete for this role, the angle's
`proof` entries lead the bullets within each role, and the skills order starts
with the categories the angle rests on. The variant records `angle:` as a
top-level key (`label:` remains accepted as its older spelling). `/setup`
derives angles *after* the entries exist — an angle written first is a slogan
looking for proof — and checks the block with `--lint-bank` before moving on.

**What does not change.** Every red line holds. Neither the scorecard nor the
angle licenses a claim: coverage is raised from evidence that already exists,
and an angle is made credible by its proof entries. No gate moves, and nothing
here runs in the unattended sweep — both belong to the interactive tailoring
path (§15, §18).
