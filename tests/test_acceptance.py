"""Phase 0 acceptance tests (PRD §11) plus the v3.1 amendments (PRD §14).

  * validate.py passes a good fixture and fails one with a missing ev
  * validate.py --cover fails a letter containing a number absent from its variant
  * the style gate fails em dashes and stock AI phrasing (resume and cover)
  * render.py emits a markdown resume and still enforces the ev floor
  * fetch.py --dry-run runs clean
  * tracker.py regeneration is byte-identical (Phase 7 invariant, checked early)
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
FIX = os.path.join(ROOT, "tests", "fixtures")


def run(script, *args):
    return subprocess.run(
        [sys.executable, os.path.join(BIN, script), *args],
        capture_output=True,
        text=True,
    )


# ── validate.py resume mode ────────────────────────────────────────────────


def test_good_variant_passes():
    r = run(
        "validate.py",
        os.path.join(FIX, "variant_good.yaml"),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--resume", os.path.join(FIX, "resume.yaml"),
    )
    assert r.returncode == 0, r.stderr


def test_missing_ev_fails():
    r = run(
        "validate.py",
        os.path.join(FIX, "variant_missing_ev.yaml"),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--resume", os.path.join(FIX, "resume.yaml"),
    )
    assert r.returncode == 1, r.stderr
    assert "no evidence ID" in r.stderr


# ── validate.py cover mode ─────────────────────────────────────────────────


def test_good_cover_passes():
    r = run(
        "validate.py",
        "--cover", os.path.join(FIX, "cover_good.md"),
        "--variant", os.path.join(FIX, "variant_good.yaml"),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
    )
    assert r.returncode == 0, r.stderr


def test_cover_bad_numeral_fails():
    r = run(
        "validate.py",
        "--cover", os.path.join(FIX, "cover_bad_numeral.md"),
        "--variant", os.path.join(FIX, "variant_good.yaml"),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
    )
    assert r.returncode == 1, r.stderr
    assert "40" in r.stderr


# ── validate.py style gate (PRD §14) ───────────────────────────────────────

# A config path that doesn't exist forces validate.py's built-in banned list,
# keeping these tests independent of the user's profile/config.yaml.
NO_CONFIG = os.path.join(FIX, "no-such-config.yaml")


def test_cover_bad_style_fails():
    r = run(
        "validate.py",
        "--cover", os.path.join(FIX, "cover_bad_style.md"),
        "--variant", os.path.join(FIX, "variant_good.yaml"),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--config", NO_CONFIG,
    )
    assert r.returncode == 1, r.stderr
    assert "banned style pattern" in r.stderr
    assert "—" in r.stderr
    assert "excited to apply" in r.stderr
    # the "It's not X, it's Y" structure is caught by regex, not substring
    assert "banned style regex" in r.stderr


def test_good_cover_passes_style_gate():
    r = run(
        "validate.py",
        "--cover", os.path.join(FIX, "cover_good.md"),
        "--variant", os.path.join(FIX, "variant_good.yaml"),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--config", NO_CONFIG,
    )
    assert r.returncode == 0, r.stderr


def test_resume_em_dash_fails(tmp_path):
    src = open(os.path.join(FIX, "variant_good.yaml"), encoding="utf-8").read()
    bad = src.replace(
        "Platform engineer who makes the paved road other teams ship on.",
        "Platform engineer — the paved road other teams ship on.",
    )
    assert bad != src
    variant = tmp_path / "variant_bad_style.yaml"
    variant.write_text(bad, encoding="utf-8")
    r = run(
        "validate.py", str(variant),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--resume", os.path.join(FIX, "resume.yaml"),
        "--config", NO_CONFIG,
    )
    assert r.returncode == 1, r.stderr
    assert "banned style pattern" in r.stderr


# ── render.py markdown mode (PRD §14) ──────────────────────────────────────


def test_render_markdown(tmp_path):
    out = tmp_path / "resume.md"
    r = run("render.py", os.path.join(FIX, "variant_good.yaml"), "-o", str(out))
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Pat Doe")
    assert "## Experience" in text
    assert "**Staff Engineer**, Example Co" in text
    assert "ev:" not in text  # evidence IDs are internal, never printed


def test_render_markdown_missing_ev_fails(tmp_path):
    out = tmp_path / "resume.md"
    r = run("render.py", os.path.join(FIX, "variant_missing_ev.yaml"), "-o", str(out))
    assert r.returncode != 0
    assert not out.exists()


# ── angles: the bank's positioning stances (PRD §21) ───────────────────────

BANK = os.path.join(FIX, "evidence-bank.md")


def write_bank(tmp_path, angles: str, entry_angles: str = "platform-leader") -> str:
    path = tmp_path / "bank.md"
    path.write_text(
        f"# Bank\n\n## Angles\n\n{angles}\n\n## Evidence\n\n"
        f"### ev:0001 — First\nconfidence: qualitative\ntags:       a-skill\n"
        f"angles:     {entry_angles}\n\n"
        f"### ev:0002 — Second\nconfidence: qualitative\ntags:       a-skill\n"
        f"angles:     {entry_angles}\n",
        encoding="utf-8",
    )
    return str(path)


def test_lint_bank_passes_a_well_formed_bank():
    r = run("validate.py", "--lint-bank", "--bank", BANK)
    assert r.returncode == 0, r.stderr
    assert "angles hold" in r.stderr


def test_lint_bank_catches_an_angle_no_entry_declares(tmp_path):
    bank = write_bank(
        tmp_path,
        "### angle: platform-leader\nclaim:  Builds the paved road.\nproof:  ev:0001, ev:0002\n",
        entry_angles="ghost-angle",
    )
    r = run("validate.py", "--lint-bank", "--bank", bank)
    assert r.returncode != 0
    assert "ghost-angle" in r.stderr


def test_lint_bank_catches_an_angle_nothing_proves(tmp_path):
    bank = write_bank(
        tmp_path,
        "### angle: thin-angle\nclaim:  A claim with one entry behind it.\nproof:  ev:0001\n",
        entry_angles="",
    )
    r = run("validate.py", "--lint-bank", "--bank", bank)
    assert r.returncode != 0
    assert "slogan" in r.stderr


def test_lint_bank_catches_a_claimless_angle(tmp_path):
    bank = write_bank(tmp_path, "### angle: platform-leader\nproof:  ev:0001, ev:0002\n")
    r = run("validate.py", "--lint-bank", "--bank", bank)
    assert r.returncode != 0
    assert "no claim line" in r.stderr


def test_legacy_bullet_angles_still_parse(tmp_path):
    # A bank written before the block format keeps working (PRD §21).
    bank = write_bank(tmp_path, "- `platform-leader` — builds the paved road.")
    r = run("validate.py", "--lint-bank", "--bank", bank)
    assert r.returncode == 0, r.stderr


def test_variant_positioned_on_an_undeclared_angle_fails(tmp_path):
    variant = tmp_path / "variant.yaml"
    variant.write_text(
        "angle: invented-angle\nsections:\n  - heading: Summary\n"
        "    bullets:\n      - text: \"Ran the platform.\"\n        ev: ev:0031\n",
        encoding="utf-8",
    )
    r = run("validate.py", str(variant), "--bank", BANK, "--resume", os.path.join(FIX, "resume.yaml"))
    assert r.returncode != 0
    assert "invented-angle" in r.stderr


def test_variant_may_still_declare_its_angle_under_the_old_label_key():
    # variant_good.yaml carries `label: platform-leader`, the original spelling.
    r = run(
        "validate.py",
        os.path.join(FIX, "variant_good.yaml"),
        "--bank", BANK,
        "--resume", os.path.join(FIX, "resume.yaml"),
    )
    assert r.returncode == 0, r.stderr


# ── fetch.py dry-run ───────────────────────────────────────────────────────


def test_fetch_dry_run_no_targets(tmp_path):
    # With no targets.yaml the dry run must still exit 0 (nothing to do).
    r = run("fetch.py", "--dry-run", "--root", str(tmp_path))
    assert r.returncode == 0, r.stderr


def test_fetch_survives_a_profile_yaml_that_is_not_a_mapping(tmp_path):
    # A hand-edited profile file that parses to a list must degrade to "no
    # targets, no role filter" with a warning, never an AttributeError.
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "targets.yaml").write_text("- example-co\n- another-co\n", encoding="utf-8")
    (profile / "goals.yaml").write_text("- a track\n", encoding="utf-8")
    r = run("fetch.py", "--dry-run", "--root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "not a mapping" in r.stderr
    assert "Traceback" not in r.stderr


def test_location_filter_matching():
    sys.path.insert(0, os.path.join(BIN, "lib"))
    from locations import location_matches

    # Placeholder place names: the filter is regex-only and knows no geography,
    # so the test exercises the shapes boards actually print, not a real region.
    patterns = [
        "riverton", "eastland", r"\bel\b", r"\bels\b", r"\bnorthshire\b",
        "lakeside", "bayview", "hillcrest", "pinegrove", "westport",
    ]
    for loc in (
        "Riverton, Northshire, Eastland",
        "EL - Riverton",
        "EL: Riverton (45 Market St)",
        "Lakeside, el",
        "Lakeside",  # some boards report a bare city, no country token
        "Remote - ELS",
        "",  # unknown location goes to triage, not the bin
    ):
        assert location_matches(loc, patterns), loc
    # Near misses the word boundaries must reject: "Elsewhere" contains "els",
    # "Riverside" is not "Riverton", and an unlisted country is out.
    for loc in ("Elsewhere, Texas", "London, UK", "US Remote", "Riverside, NZ"):
        assert not location_matches(loc, patterns), loc
    # No filter configured -> keep everything.
    assert location_matches("London, UK", [])


def test_freshness_filter():
    sys.path.insert(0, os.path.join(BIN, "lib"))
    from datetime import datetime, timezone

    from freshness import is_fresh, parse_updated_at

    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    # Fresh, across the formats the adapters actually emit.
    for value in (
        "2026-07-01T00:00:00Z",          # greenhouse/ashby/smartrecruiters ISO
        "2026-07-01T00:00:00+02:00",     # ISO with offset
        "2026-07-01",                    # workable bare date
        "1782864000000",                 # lever epoch millis (2026-07-01)
        "1782864000",                    # epoch seconds
        "",                              # unknown age goes to triage, not the bin
        "not-a-date",                    # unparseable likewise
    ):
        assert is_fresh(value, 30, now=now), value
    # Stale: last touched more than 30 days before `now`.
    for value in (
        "2026-06-01T00:00:00Z",
        "2026-01-15",
        "1743465600000",                 # 2025-04-01 in epoch millis
    ):
        assert not is_fresh(value, 30, now=now), value
    # 0 disables the filter entirely.
    assert is_fresh("2020-01-01", 0, now=now)
    # Unparseable values must read as unknown, never as a date.
    assert parse_updated_at("someday") is None
    assert parse_updated_at("") is None


# ── schema.py null-coalescing (adapter robustness) ─────────────────────────


def test_posting_coerces_null_fields():
    # An ATS payload with an explicit null for a read field must not sink the
    # whole board: Posting coerces None -> "" so one bad field costs nothing.
    sys.path.insert(0, os.path.join(BIN, "lib"))
    from schema import Posting

    p = Posting(
        source="greenhouse", slug="acme", company="acme",
        title=None, location=None, url=None, department=None,
        updated_at=None, description=None,
    )
    assert p.title == "" and p.location == "" and p.description == ""
    # A fingerprint is still derivable (no crash on the None-turned-empty).
    assert len(p.fingerprint()) == 64


# ── render.py contact links (list-valued fields) ───────────────────────────


def test_render_flattens_contact_links(tmp_path):
    variant = tmp_path / "variant.yaml"
    variant.write_text(
        "name: Pat Doe\n"
        "contact:\n"
        "  email: pat@example.com\n"
        "  links:\n"
        "    - github.com/pat\n"
        "    - linkedin.com/in/pat\n"
        "sections:\n"
        "  - heading: Summary\n"
        "    bullets:\n"
        "      - text: Builds reliable systems.\n"
        "        ev: ev:0001\n",
        encoding="utf-8",
    )
    out = tmp_path / "resume.md"
    r = run("render.py", str(variant), "-o", str(out))
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    # Each link appears as its own entry, never as a Python list repr.
    assert "github.com/pat" in text
    assert "linkedin.com/in/pat" in text
    assert "['" not in text and "']" not in text


# ── _http.py retry scope (fail fast on non-retryable 4xx) ──────────────────


def test_http_fails_fast_on_404(monkeypatch):
    sys.path.insert(0, os.path.join(BIN, "lib"))
    import time as _time

    import httpx

    from sources import _http

    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        req = httpx.Request(method, url)
        return httpx.Response(404, request=req, json={"error": "not found"})

    slept = {"n": 0}
    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setattr(_time, "sleep", lambda *_: slept.__setitem__("n", slept["n"] + 1))

    try:
        _http.get_json("https://boards-api.greenhouse.io/v1/boards/nope/jobs")
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("expected a 404 to raise")
    # One attempt, no retries, no backoff sleeps for a genuine 404.
    assert calls["n"] == 1, calls
    assert slept["n"] == 0, slept


def test_http_retries_on_500(monkeypatch):
    sys.path.insert(0, os.path.join(BIN, "lib"))
    import time as _time

    import httpx

    from sources import _http

    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        req = httpx.Request(method, url)
        return httpx.Response(503, request=req, json={})

    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setattr(_time, "sleep", lambda *_: None)

    try:
        _http.get_json("https://boards-api.greenhouse.io/v1/boards/x/jobs")
    except httpx.HTTPStatusError:
        pass
    # A 5xx is transient: it exhausts MAX_RETRIES attempts.
    assert calls["n"] == _http.MAX_RETRIES, calls


# ── fetch.py location_filter validation ────────────────────────────────────


def test_fetch_rejects_bad_location_regex(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "targets.yaml").write_text(
        "companies:\n  - slug: acme\n    ats: greenhouse\n"
        "location_filter:\n  - '['\n",  # unbalanced bracket -> re.error
        encoding="utf-8",
    )
    r = run("fetch.py", "--dry-run", "--root", str(tmp_path))
    assert r.returncode == 2, r.stderr
    assert "invalid location_filter regex" in r.stderr


# ── tracker.py determinism (Phase 7 invariant) ─────────────────────────────


def test_tracker_regeneration_identical(tmp_path):
    applied = tmp_path / "applied" / "2026-07-17_example_staff-eng"
    applied.mkdir(parents=True)
    (applied / "meta.yaml").write_text(
        "company: Example Co\n"
        "title: Staff Engineer\n"
        "date: 2026-07-17\n"
        "applied: 2026-07-17\n"
        "status: applied\n"
        "url: https://example.com/job\n"
    )
    out = tmp_path / "tracker.csv"
    r1 = run("tracker.py", "--root", str(tmp_path), "-o", str(out), "--today", "2026-07-20")
    assert r1.returncode == 0, r1.stderr
    first = out.read_bytes()
    out.unlink()
    r2 = run("tracker.py", "--root", str(tmp_path), "-o", str(out), "--today", "2026-07-20")
    assert r2.returncode == 0, r2.stderr
    assert out.read_bytes() == first


def test_tracker_auto_ghost(tmp_path):
    applied = tmp_path / "applied" / "2026-01-01_old_role"
    applied.mkdir(parents=True)
    (applied / "meta.yaml").write_text(
        "company: Old Co\ntitle: Engineer\ndate: 2026-01-01\napplied: 2026-01-01\nstatus: applied\n"
    )
    out = tmp_path / "tracker.csv"
    run("tracker.py", "--root", str(tmp_path), "-o", str(out), "--today", "2026-03-01")
    assert "ghosted" in out.read_text()


# ── goals: role filter + skills alias (PRD §19) ────────────────────────────


def test_role_filter_matching():
    sys.path.insert(0, os.path.join(BIN, "lib"))
    from roles import title_matches

    patterns = ["data analyst", "business analyst", "analytics", r"\binsights\b"]
    for title in (
        "Data Analyst",
        "Senior Business Analyst",
        "Analytics Engineer",
        "Insights Manager",
        "",  # unknown title goes to triage, not the bin
    ):
        assert title_matches(title, patterns), title
    for title in ("Registered Nurse", "Warehouse Associate", "Account Executive"):
        assert not title_matches(title, patterns), title
    # No filter configured -> keep everything (the default: off).
    assert title_matches("Registered Nurse", [])


def test_load_goals_missing_file(tmp_path):
    sys.path.insert(0, os.path.join(BIN, "lib"))
    from roles import load_goals, role_filter

    # An absent goals.yaml is a valid state (it arrives during /setup).
    assert load_goals(str(tmp_path)) == {}
    assert role_filter(load_goals(str(tmp_path))) == []


def test_skills_key_is_a_synonym_for_technologies(tmp_path):
    # A nurse's variant lists clinical competencies, not technologies. Both key
    # names must validate and render identically.
    import yaml

    src = yaml.safe_load(open(os.path.join(FIX, "variant_good.yaml"), encoding="utf-8"))
    assert src.get("technologies"), "fixture should exercise the legacy key"
    src["skills"] = src.pop("technologies")
    variant = tmp_path / "variant_skills_key.yaml"
    variant.write_text(yaml.safe_dump(src, sort_keys=False), encoding="utf-8")

    r = run(
        "validate.py", str(variant),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--resume", os.path.join(FIX, "resume.yaml"),
        "--config", NO_CONFIG,
    )
    assert r.returncode == 0, r.stderr

    out = tmp_path / "resume.md"
    r = run("render.py", str(variant), "-o", str(out))
    assert r.returncode == 0, r.stderr
    assert "## Skills" in out.read_text(encoding="utf-8")


def test_unbacked_skill_still_fails(tmp_path):
    # The provenance gate must not weaken under the new key name.
    import yaml

    src = yaml.safe_load(open(os.path.join(FIX, "variant_good.yaml"), encoding="utf-8"))
    src.pop("technologies", None)
    src["skills"] = ["Underwater Basket Weaving"]
    variant = tmp_path / "variant_bad_skill.yaml"
    variant.write_text(yaml.safe_dump(src, sort_keys=False), encoding="utf-8")

    r = run(
        "validate.py", str(variant),
        "--bank", os.path.join(FIX, "evidence-bank.md"),
        "--resume", os.path.join(FIX, "resume.yaml"),
        "--config", NO_CONFIG,
    )
    assert r.returncode == 1, r.stderr
    assert "Underwater Basket Weaving" in r.stderr


# ── template hygiene (PRD §19.2) ───────────────────────────────────────────


def test_template_carries_no_personal_data():
    r = run("check_template_clean.py", "--root", ROOT)
    assert r.returncode == 0, r.stderr


def test_template_guard_catches_personal_data(tmp_path):
    (tmp_path / "profile").mkdir()
    (tmp_path / "profile" / "evidence-bank.md").write_text("### ev:0001\n", encoding="utf-8")
    r = run("check_template_clean.py", "--root", str(tmp_path))
    assert r.returncode == 1, r.stderr
    assert "evidence-bank.md" in r.stderr
