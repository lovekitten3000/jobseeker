# Jobseeker

**A job-search assistant that runs inside Claude Code.** It finds job postings,
drafts a tailored resume and cover letter for the ones you pick, checks every
claim against facts you provided, and keeps a tracker of where each application
is up to. You review everything, and **you always click "apply" yourself, in
your own browser**.

It works from **where you want to go**, not just where you've been — so it fits
a graduate, a career changer, and someone after the next rung of the same
ladder equally well. Whatever your field.

**It assumes nothing about you.** No industry, no seniority, no country, no
list of skills. Every example value you'll find in here is a blank to fill in,
and everything the system judges a job by comes from answers you give it during
setup.

MIT licensed — copy it, change it, keep it.

---

## What it does

Think of it as a very careful assistant that:

- **Knows what you're aiming at.** Setup asks you to name one to three *career
  tracks* — the jobs you actually want, in your words. Everything downstream
  scores roles against those, not against your last job title. If a track is a
  **change of direction**, you say so, name the experience that genuinely
  carries across, and name what you're missing; drafts then lead with the
  transferable work and state the gap plainly instead of writing around it.
- **Finds roles for you.** Either you paste in a job ad you found anywhere
  (`/add`), or an optional nightly sweep checks the public job boards of
  companies you choose and leaves you a morning shortlist.
- **Drafts for you.** For the roles you pick, it writes a tailored resume and
  cover letter in plain markdown, easy to read on your phone.
- **Writes for the screening software, then for the human.** Most applications
  are read by keyword-matching software first. A checker reads the job ad,
  works out which words that employer keeps repeating, and reports exactly
  which of them your draft uses — so the fix is a real one, not a guess. It
  will re-word your own experience in the employer's language and pull forward
  the evidence that proves the point, and it will never add a skill you don't
  have: anything it can't cover honestly is written down as a gap for you to
  see. It also flags a word repeated so often the draft reads as stuffed,
  because a person reads it after the software does.
- **Never makes things up.** Every claim in every draft must trace back to a
  fact *you* told it during setup. An automated checker blocks drafts that
  invent numbers, employers, or technologies, and even bans AI-sounding
  phrases so letters read like you wrote them.
- **Tracks everything.** A simple spreadsheet (`tracker.csv`) shows every
  application and its status. It updates itself; you never edit it.

## Which job boards the sweep can reach

The sweep only ever talks to the **official public job-listing APIs** that
companies' own careers pages are built on — never LinkedIn, Indeed, or
anything behind a login. Today it covers ten of these systems, which between
them power most mid-to-large employers' careers pages:

**Greenhouse · Lever · Ashby · Workable · SmartRecruiters · Recruitee ·
Workday · Oracle Recruiting Cloud · PageUp · Teamtailor**

**What it deliberately can't reach — and why:**

- **LinkedIn, Indeed, Seek, Glassdoor, and anything behind a login.** These
  forbid scraping and need an account; reaching them would break the "never
  scrape, never log in" rule the whole system is built on. Found a role there?
  Just paste it in with **`/add`** — same honest draft, same review.
- **Employers on a job system not in the list above.** A few older or niche
  systems publish no open API. Each system the sweep supports is one small
  adapter file, so a new one can be added when it's worth it; until then those
  boards are reached the same way — by hand, with `/add`.
- **Even on the boards it does cover, the sweep shows you less on purpose.**
  It skips anything outside your locations, older than 30 days, already seen in
  a past run, or scoring below your quality bar — so the morning shortlist is
  only fresh, in-region, unseen roles worth a look, not every opening.

The takeaway: the sweep is a **wide first pass** across the boards it can reach
automatically, and **`/add`** covers everything else. Nothing good is lost — it
just arrives by a different door.

## What it will never do

These rules are built in and non-negotiable:

- **Never submits an application.** You apply by hand, every time.
- **Never invents or exaggerates** a metric, job title, date, or skill.
- **Never scrapes** LinkedIn, Indeed, or anything behind a login.
- If it doesn't know something about you, it **asks** instead of guessing.
- If you're missing something a role wants, it **says so plainly** instead of
  papering over it.

## What you need

- A **GitHub account** (free) — your copy of this system lives in a GitHub
  repository.
- **Claude Code** — the easiest way is Claude Code on the web at
  [claude.ai/code](https://claude.ai/code), which needs a paid Claude plan.
  No API keys, no extra costs, nothing to install on your computer.

You do **not** need to know how to code. Everything is driven by typing
simple commands like `/setup` and `/add` into a Claude Code chat.

## Set it up (one time, ~30 minutes plus the interview)

1. **Make your own private copy.** On this repository's GitHub page, click
   **Use this template → Create a new repository**. Name it something like
   `my-jobseeker` and set it to **Private**. Private matters: your copy will
   hold your real career history. (If you don't see the "Use this template"
   button, ask the person who shared this with you to enable it, or fork the
   repo and make your fork private.)
2. **Open it in Claude Code.** Go to [claude.ai/code](https://claude.ai/code)
   and connect your new private repository.
3. **Configure the environment** (only needed for the automated sweep, but
   quick): follow `docs/ENVIRONMENT.md` — it's a copy-paste of a short list of
   allowed websites and a 4-line setup script into the environment settings.
4. **Run `/setup`.** This is the big one. Claude asks first about **where you
   want to go** (your career tracks — 20 minutes), then interviews you about
   your career a few questions at a time to build your "evidence bank": the
   master list of everything true about you that all future resumes draw from.
   Budget a relaxed hour or three; you can stop and pick it up later. Honest
   answers matter more than impressive ones — the system is designed so drafts
   can only use what's in the bank. Not every accomplishment needs a number,
   and a shorter honest bank beats a padded one.
5. **Try it.** Find a job ad anywhere, run `/add`, and paste the ad in.
   You'll get an honest fit read, and if you say "go", a tailored draft to
   review right there in the chat.

Lost at any point? Type **`/next`** — it looks at where things stand and
tells you the one best thing to do now.

## The everyday workflow

### When you find a job yourself (most common)

1. **`/add`** — paste the job ad. Claude reads it, scores the fit honestly
   (including what the role wants that you don't have), and asks if you want
   to pursue it.
2. **Review together.** If yes, it drafts the resume and cover letter and
   walks them with you line by line. It will ask you questions where it's
   unsure rather than guess; your answers are saved so it never asks twice.
3. **Apply by hand.** Open the company's site in your browser and submit the
   application yourself, using the approved drafts.
4. **`/log`** — tell it "I applied". The tracker updates itself. Later, when
   you hear back (or don't), one more `/log` line records it. Silence
   eventually auto-marks the role "ghosted" with no effort from you.

### With the automatic sweep turned on (optional)

1. **Add target companies** to `profile/targets.yaml` (the `/setup` interview
   helps with this), then create the scheduled routine by copy-pasting the
   prompt from `docs/ROUTINE.md`. Each weekday morning the sweep checks those
   companies' job boards and leaves you a shortlist report.
2. **`/choose`** — over coffee, skim the shortlist and pick the keepers.
   "None of these" is a fine answer; rejected roles never come back.
3. **`/tailor`** — drafts resumes and cover letters for your picks only, and
   reviews them with you live, same as `/add`.
4. **Apply by hand, then `/log`.** Same as always.

## The commands

| Command | What it does |
|---|---|
| `/setup` | One-time interview that builds your profile and evidence bank |
| `/add` | Paste in a job ad you found; fit read + tailored draft in one sitting |
| `/next` | "What should I do now?" — reads the state of play, gives you one next step |
| `/choose` | Morning pick: which shortlisted roles are worth tailoring? |
| `/tailor` | Write the resume + cover letter for the roles you kept |
| `/review` | Re-open a draft you deferred and finish reviewing it |
| `/log` | Record "I applied" or any status change, in about two minutes |
| `/sweep` | The nightly search itself (normally run by the schedule, not by you) |

## What's in the folders

```
profile/     Everything about you (starts empty; /setup fills it in)
queue/       Roles in flight: the sweep's shortlist and your ready-to-send drafts
applied/     Roles you've applied to (created by /log)
tracker.csv  The self-maintaining application tracker
templates/   Blank starting points the system copies from
docs/        The two copy-paste setup guides (environment + schedule)
bin/         The scripts that fetch postings and fact-check drafts
.claude/     The commands and rules Claude follows
PRD.md       The full design document, if you're curious how it all works
CLAUDE.md    The safety rules Claude must obey in this repo
```

## Changing direction, or aiming at two things at once

Your career tracks live in `profile/goals.yaml`, and they are meant to be
edited. Open it (or just ask Claude in a session) when:

- **You're pivoting.** Set `pivot: true` on the track, write `transferable` —
  which of your experience genuinely carries across, in your own words — and
  `known_gaps`, what you plainly don't have yet. Both are honest-answer
  fields. A padded `transferable` produces a resume that wins an interview you
  can't survive, which is the one thing this system exists to prevent.
- **You're open to two directions.** Add a second track. The shortlist is
  grouped by track so you can see how each is doing. Three is the practical
  limit; past that the shortlist stops meaning anything.
- **A track keeps coming up empty.** Usually its `titles` are too narrow, or
  no company in `targets.yaml` hires for it. `/next` will point this out.

Nothing edits this file but you. Claude reads your goals, reports when a track
isn't working, and leaves the decision alone.

## Getting improvements later

Your copy is a snapshot. Fixes made to the template afterwards don't reach it
by themselves — ask Claude in a session:

> Pull the latest changes from the upstream template, but keep everything in
> `profile/`, `queue/`, `applied/`, `state/` and `tracker.csv` exactly as it is.

(Under the hood that's `git remote add upstream <template-url>` then a fetch
and merge. Your data lives in directories the template never touches, so
conflicts are rare and confined to `bin/`, `.claude/`, `docs/` and `templates/`.)

## Sharing it on

Point people at the template repo, not at your copy — your copy has your career
history in it. They click **Use this template**, make it **private**, and run
`/setup`. Their goals, evidence, and companies are entirely their own; nothing
about your search is carried across.

## Good to know

- **Your data stays in your private repo.** This template contains no
  personal data (CI enforces that), and your copy should stay private because
  it will.
- **Everything is saved in Git automatically.** Every draft, decision, and
  status change is committed, so nothing is ever lost and you can always see
  history on GitHub.
- **It's honest by design.** The fact-checker catches invention (made-up
  numbers, employers, technologies). What it can't catch is *stretching* a
  real fact — that's what your review is for. When in doubt, tone it down.
- **Costs nothing beyond your Claude subscription.** The job-board checks use
  free public APIs; there are no API keys anywhere in the system.

## For technical users

```bash
pip install --break-system-packages typst pyyaml httpx pydantic pytest
python3 -m pytest tests/            # acceptance tests
python3 bin/fetch.py --dry-run      # fetch + dedupe, writes nothing
python3 bin/seen.py status          # what the dedupe index has seen
python3 bin/validate.py <variant.yaml>
python3 bin/validate.py --lint-bank      # the bank's angles: claimed, proved, used
python3 bin/ats_score.py --jd jd.md --variant <variant.yaml>   # keyword coverage
python3 bin/check_template_clean.py # template-repo guard (fails in your instance, by design)
```

The full design and rationale live in `PRD.md` (§19 covers career tracks and
what changed to make this shareable, §20 why nothing in here is filled in for
you); the operating rules and red lines in `CLAUDE.md`.

---

Released under the MIT License — see `LICENSE`.
