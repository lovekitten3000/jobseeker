# Your profile lives here

This folder is empty on purpose. It gets filled in when you run **`/setup`**
in a Claude Code session — an interview that builds everything the system
knows about you:

| File | What it is | Created by |
|---|---|---|
| `goals.yaml` | **Where you want to go** — one to three career tracks, and whether each is a change of direction. Written first, because it decides what everything else is measured against | `/setup` (from `templates/goals.example.yaml`) |
| `evidence-bank.md` | Your "master resume" — every job, project, and accomplishment, each with an ID and an honesty rating. **Where you have been**. Its `## Angles` block holds your positioning: each one a claim about what you're for, and the evidence that proves it — the **argument** a tailored resume makes | `/setup` |
| `resume.yaml` | The canonical facts: every employer, title, and date, exactly once | `/setup` |
| `voice.md` | A short description of how you write, so drafts sound like you | `/setup` |
| `config.yaml` | Your preferences: salary floor, locations, dealbreakers, scoring threshold | `/setup` (from `templates/config.example.yaml`) |
| `targets.yaml` | The companies whose job boards the automated sweep watches | `/setup` (from `templates/targets.example.yaml`) |
| `companies/<name>.md` | Three honest lines about why you'd join each company you care about | you, with help from `/setup` |
| `manual-postings/` | Job ads you found yourself and pasted in with `/add` | `/add` |
| `connections.csv` | (Optional) your LinkedIn connections export, for spotting referral paths | you |

Never edit these by hand unless you want to — every skill knows how to
maintain them for you. The one worth revisiting yourself is `goals.yaml`: it's
the only file nothing else will ever change, because what you're aiming at is
your call. Open it whenever your plans shift.

**Privacy note:** this folder will contain your real career history. That is
why your copy of this repository must be **private** (see the README's setup
steps).
