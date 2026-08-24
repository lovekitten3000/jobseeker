---
name: setup
description: Onboard a new user. Interviews them in small batches to build the evidence bank (the master resume), then their voice, constraints, and targets. This is the whole onboarding — no code editing, no terminal, no PRD reading.
---

# /setup — the whole onboarding (PRD §11 Phase 2, §12)

You are turning a fresh private instance into a working system. The user has a
browser and a phone, nothing else. No code edits. Your job is to fill
`profile/`. Do it by **interview, in batches of 3–5 questions — never a wall**.

**You do not know this person.** Do not assume their field, their seniority, or
that their work produces numbers. The interview is the same shape for a
graduate nurse, a career-changing teacher, and a staff engineer; the content is
entirely theirs. Ask, never fill in.

## What you're building (in order)

### 1. `profile/goals.yaml` — where they want to GO (20 minutes, do it first)
Copy `templates/goals.example.yaml`. **Every value in it is an angle-bracketed
placeholder** — there is no default track, no default field, no default
seniority, and none of it is a suggestion. Replace all of them with the user's
own words; never leave one standing, and never fill one in on their behalf.

This comes **before** the evidence bank, and the order is load-bearing: the
goal decides which evidence is worth digging for, and without it triage can
only recognise the job they already have.

Interview for one to three **tracks**. Per track: `label` (how they'd describe
the job to a friend), `titles` (the title words employers actually use — push
for the variants, not just the tidy one), `seniority` **for them** (student,
graduate, early, mid, senior, lead, exec, returner), `why` in one honest line,
and `must_have` / `avoid`.

Then the question that decides everything downstream: **is this track a
pivot?** Have they done this kind of work before, or are they moving into it?

- **Not a pivot** → `pivot: false`. Their history is the support.
- **A pivot** → `pivot: true`, and you must fill in `transferable` (which of
  their experience genuinely carries across, in their words) and `known_gaps`
  (what they plainly don't have yet). Both are honest-answer fields: a padded
  `transferable` produces a resume that wins an interview they can't survive,
  which is the one outcome this system exists to prevent. Get the real answer,
  write it down, and let the gaps be gaps.

Leave `supporting_angles` empty for now — you fill it in after the bank exists
(step 3). Leave `role_filter` out entirely unless they ask for it; it is opt-in
and it can drop good roles.

Commit this before moving on.

### 2. `profile/evidence-bank.md` — the master resume (the long one)
This is the source of truth every resume is capped by. Exhaustive by design.
Interview the user story by story, **steered by the tracks you just wrote**: on
a pivot, dig hardest at the experience their `transferable` line points to,
because that is the material every draft will lead with and it is usually
buried in a job that was called something else.

For each accomplishment, capture an `### ev:NNNN` entry (see
`templates/evidence-entry.md`) with:
- `role` (must match an employer you'll record in resume.yaml)
- `dates`, `metric`, `scope`, `tags`, `angles`, `narrative`
- `confidence`: **measured** (a real number with a source — record the source),
  **estimated** (a number you believe but can't cite — phrase directionally),
  or **qualitative** (no number). Be honest; this field is load-bearing and the
  linter enforces it.

**How many entries is enough** depends on how much career there is. Aim for
the range that fits them, and stop when new questions stop producing new
material rather than when a counter hits a number:

| Where they are | Realistic target |
|---|---|
| Student / graduate / first job | 10–20 — coursework, projects, part-time work, volunteering, societies all count |
| Career changer | 20–40, weighted toward whatever supports the pivot track |
| Early career (1–4 years) | 20–35 |
| Mid career (5–12 years) | 35–60 |
| Senior / long career / returner | 50+, and prune ruthlessly rather than skip |

A thin bank caps every later phase, so keep interviewing while the answers are
still yielding. But a graduate with 14 honest entries has a complete bank, and
telling them otherwise just teaches them to embellish.

**Not every accomplishment has a number, and that is fine.** `confidence:
qualitative` is a first-class value, not a failure — plenty of real work (care,
teaching, design, craft, coordination, safety) is judged by outcome, not
metric. Never push someone to produce a number they don't have; the linter will
strip a fabricated one out of the draft anyway, and the honest qualitative
version is stronger than a hedged fake.

`tags` are whatever their field calls its capabilities — software, machinery,
clinical procedures, languages, curricula, certifications, methods, tools.
They are not "technologies" unless that's their line of work.

Then write a non-empty `## Shortfalls` — things target roles ask for that the
user doesn't have. If Shortfalls is empty, they weren't honest, and triage will
be worthless. On a pivot track, the track's `known_gaps` belong here too.
Nothing is ever deleted from the bank; obsolete entries get `status: retired`.

#### Angles — the argument each resume will make (PRD §21)

An **angle** is a positioning stance: one claim about what this person is
*for*, proved by at least two evidence entries, aimed at a track. Three sit
side by side in the system and are not interchangeable — the **track** is the
job they're applying for, the **evidence** is what they've actually done, and
the **angle** is the argument connecting the two. Every draft picks one, and
that choice sets the summary's first line and which bullets lead.

Derive them *after* the entries exist, never before: an angle invented first is
a slogan looking for proof. Read back what the bank now holds and ask the user
which of these they'd want a stranger to conclude about them. Aim for 3+ —
enough that different postings get genuinely different arguments — and write
each one into the bank's `## Angles` block (`templates/angle-entry.md`):

```
### angle: <slug>
claim:  <one line, their words: what they are for>
proof:  ev:0031, ev:0044        # two or more entries that demonstrate it
serves: <track ids from goals.yaml this angle argues for>
```

Then tag every relevant evidence entry with the angle slug in its `angles:`
field, and map each track's `supporting_angles` to the slugs that serve it.

Two questions catch a weak angle before it reaches a resume: *which two
entries prove this?* (fewer than two and it is a slogan — cut it or dig for
the evidence) and *which track does it argue for?* (none and it will never be
chosen). Check the whole block deterministically before moving on:

```
python3 bin/validate.py --lint-bank
```

It fails on an angle nothing proves, an angle with no claim, and an entry that
cites an angle the bank never declared. It cannot tell you whether an angle is
a *good* pitch — that is the user's call, and it is worth asking them out loud.

### 3. `profile/resume.yaml` — canonical facts
Every employer, title, and date, exactly once. Variants must match this.

### 4. `profile/voice.md` — tone
A short description of how the user writes: plain vs. formal, dry vs. warm,
first-person cover voice. This is the tailor's TONE parameter, written once.

### 5. `profile/config.yaml` — behaviour
Copy `templates/config.example.yaml`. Interview for `constraints` (comp floor
in their own currency, remote, locations as their boards print them,
dealbreakers in their own words), `scoring.threshold`, `scoring.queue_cap`,
`cover.max_words`, `tracker.ghost_days`. The template defaults for
`scoring.near_miss_band` / `scoring.near_miss_cap` (the tier that surfaces the
closest below-threshold roles at Gate 1 so a thin night isn't silent) are
sensible as-is — mention they exist and can be tuned, but don't belabour them;
set `near_miss_band: 0` if the user wants triage to be a hard cut.

### 6. `profile/targets.yaml` — companies (Phase 4)
Copy `templates/targets.example.yaml`. For each company the user names, find its
ATS + board slug (ask them to paste the careers-page URL). For the top ~20, have
them write `profile/companies/<slug>.md` — three honest lines on why they'd go
(PRD §4.3). If they can't write three honest lines, the company doesn't belong.

Ask for companies that hire for **each** track, not just the first one. A
pivot track with no employers behind it produces a permanently empty section of
every shortlist. And warn them plainly if their field is unlikely to be on the
supported ATSes at all (public sector, healthcare systems, education,
small local employers often are not): that is not a failure, it means their
system is `/add`-driven and the sweep is a bonus. Set expectations now rather
than letting three silent mornings do it.

Two ways to check a company before committing to it, both cheap:
`python3 bin/fetch.py --dry-run` after adding it, or just paste the careers URL
and read the slug off it.

### 7. `profile/connections.csv` (optional)
LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections.
Commit the CSV. It matches referral paths against each job's company.

## After each section
Commit it. In a cloud session, committed is the only kind of existing (PRD §5.2).

Then have the user hand-match 3 real JDs against the bank — **JDs from their
target tracks**, including a pivot track if they have one. Can't find support?
Either the bank is thin (go back and interview more) or the track is further
from their evidence than the `transferable` line claimed (go back and make that
line honest). Both are better found now than in a draft. Every later phase is
capped by these two files.

Close by telling them the one next thing: `/add` a real posting they've been
sitting on, and see the whole loop run once.
