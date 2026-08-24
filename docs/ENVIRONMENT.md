# Environment setup (paste-in) — PRD §7

Configured once, in the web UI, at the environment selector (the cloud icon).
No CLI required.

## 1. Network access — Custom allowlist (PRD §7.1)

Default **Trusted** does not include any ATS host, so nothing works until you
switch to **Custom**. Select Custom, tick **"Also include default list of
common package managers"** (you need PyPI for Typst), and add these hosts:

```
boards-api.greenhouse.io
api.lever.co
api.ashbyhq.com
apply.workable.com
api.smartrecruiters.com
jobs.ashbyhq.com
```

These five hosts cover the five common ATSes (Greenhouse, Lever, Ashby,
Workable, SmartRecruiters). The sweep silently reaches only the boards whose
host is on the allowlist — an adapter blocked by the network policy logs a
warning and the run continues (the sweep names failed boards in its report,
PRD §17.4), so a missing host reads as "that board found nothing", not an
error. If you add none of the boards below, you need nothing more.

**Additional ATS hosts — add only the ones you actually target.** The
repo ships adapters for five more providers (`recruitee`, `workday`,
`oracle`, `pageup`, `teamtailor` — see `templates/targets.example.yaml`).
They reach different hosts, several of them per-tenant subdomains, so add a
host only when a company in your `targets.yaml` uses that ATS:

```
*.recruitee.com          # recruitee  (each company is <slug>.recruitee.com)
*.myworkdayjobs.com      # workday    (tenant.<dc>.myworkdayjobs.com)
*.oraclecloud.com        # oracle     (the Fusion pod host in your slug)
careers.pageuppeople.com # pageup
```

`teamtailor` boards are served from each company's **own** careers host (e.g.
`careers.mantelgroup.com.au`), so there is no single host to add — allowlist
that company's careers domain when you target it. If your allowlist UI does
not accept `*.` wildcards, add the exact subdomain from the board's URL
instead. A board whose host you did not add simply returns nothing; nothing
breaks.

**Avoid Full — for the sweep's environment.** A tight allowlist is a
structural guarantee that an unattended agent can't POST your data somewhere
unexpected. This is the constraint that makes sweep-time company research
impossible — and that trade is deliberate: the sweep only searches, so it
needs only the ATS hosts.

Interactive `/tailor` and `/add` sessions are different: the human is present,
and the tailor is allowed to research the target company on the public web
(PRD §16 — findings are written to `profile/companies/<slug>.md` with source
URLs before use; LinkedIn/Indeed/anything behind auth stays banned). Run those
sessions in an environment with broader network access, or keep this locked
one and the tailor will simply skip research and say so. Attach the **locked
allowlist environment to the routine** either way.

### The two-environment setup (one-time, ~2 min)

1. Keep the environment above exactly as configured — allowlist of ATS hosts,
   setup script. Call it e.g. `jobseeker-sweep`. The **routine** stays attached
   to this one.
2. Create a second environment for the same repo: identical setup script, but
   Network access = **Full** (or Trusted). Call it e.g. `jobseeker-interactive`.
3. When you open a session to run `/tailor` or `/add`, pick
   `jobseeker-interactive` in the environment selector (the cloud icon). The
   6am sweep keeps using `jobseeker-sweep`.

Forgetting this costs nothing but research: `/tailor` in the locked
environment still works — the cover just opens on the role, and the report
says research was skipped.

## 2. Setup script (PRD §7.2)

Runs as root on Ubuntu 24.04 before Claude starts. Cached, then reused; rebuilt
when you edit it or the allowlist, and roughly weekly. Keep it under ~5 minutes.

```bash
#!/bin/bash
set -euo pipefail
pip install --break-system-packages typst pyyaml httpx pydantic
python3 -c "import typst, yaml, httpx, pydantic"
```

**No `|| true`.** It swallows a failed Typst install, and then a 6am sweep
produces roles and cover letters with no PDFs and no error anywhere. Fail at
build time, loudly.

**The Typst gotcha:** do NOT try to install the Typst GitHub *release binary* —
the GitHub proxy limits release-asset requests to repositories attached to your
session, and `typst/typst` isn't yours, so it will 403. `pip install typst`
pulls the compiler from PyPI (on the default allowlist) in seconds. Already in
the image: Python 3.x, pip, uv, ruff, pytest, jq, ripgrep, Docker, Postgres.

## 3. No secrets (PRD §7.3)

There is nothing to store. ATS APIs are public. GitHub auth is handled by the
proxy outside the sandbox. If you find yourself wanting to put a key in the
environment, reconsider the feature — a system that needs no secrets can't leak
them.

## Verify (Phase 1 acceptance)

In a web session on your private instance, both must succeed:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/stripe/jobs" | head -c 200
python3 -c "import typst; print('typst ok')"
```

If either fails, everything downstream is wasted effort — fix it before Phase 2.
