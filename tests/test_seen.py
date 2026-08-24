"""Seen-state / dedupe hardening tests (PRD §6, §8.1).

  * fingerprints are stable across casing, spacing, and dash noise
  * dedupe() drops previously-seen and within-batch duplicates
  * seen.py mark writes a shard, is idempotent, and check finds the entry
  * seen.py audit fails when a swept queue entry has no seen record
    (the exact bug that lets a sweep re-triage the same job)
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, os.path.join(BIN, "lib"))

from dedupe import dedupe  # noqa: E402
from schema import Posting  # noqa: E402


def run(script, *args):
    return subprocess.run(
        [sys.executable, os.path.join(BIN, script), *args],
        capture_output=True,
        text=True,
    )


def posting(**overrides):
    base = dict(
        source="greenhouse",
        slug="acme",
        company="Acme",
        title="Staff Engineer",
        location="Riverton",
        url="https://example.com/jobs/1",
    )
    base.update(overrides)
    return Posting(**base)


def write_raw(tmp_path, p, name="p.json"):
    raw = tmp_path / "queue" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / name
    path.write_text(json.dumps(p.model_dump()), encoding="utf-8")
    return str(path)


# ── fingerprint stability ──────────────────────────────────────────────────


def test_fingerprint_ignores_case_spacing_dashes():
    a = posting(title="Staff Engineer", company="Acme", location="Riverton")
    b = posting(title="  staff—engineer ", company="ACME", location=" RIVERTON ")
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_keeps_seniority_and_location_distinct():
    a = posting(title="Staff Engineer")
    assert a.fingerprint() != posting(title="Senior Engineer").fingerprint()
    assert a.fingerprint() != posting(location="Lakeside").fingerprint()


# ── dedupe() ───────────────────────────────────────────────────────────────


def test_dedupe_drops_seen_and_batch_duplicates():
    a, b = posting(), posting(title="Other Role")
    dup_of_a = posting(title=" STAFF  ENGINEER ")
    out = dedupe([a, dup_of_a, b], seen={b.fingerprint()})
    assert out == [a]


# ── seen.py CLI round trip ─────────────────────────────────────────────────


def test_mark_then_check_and_status(tmp_path):
    raw = write_raw(tmp_path, posting())
    r = run("seen.py", "mark", "--disposition", "killed",
            "--date", "2026-07-17", "--root", str(tmp_path), raw)
    assert r.returncode == 0, r.stderr
    shard = tmp_path / "state" / "seen" / "2026-07-17.jsonl"
    assert shard.exists()
    row = json.loads(shard.read_text().strip())
    assert row["fingerprint"] == posting().fingerprint()
    assert row["disposition"] == "killed"

    r = run("seen.py", "check", "--root", str(tmp_path), raw)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SEEN" in r.stdout

    r = run("seen.py", "status", "--root", str(tmp_path))
    assert r.returncode == 0
    assert "1 unique fingerprint" in r.stdout
    assert "killed: 1" in r.stdout


def test_mark_is_idempotent(tmp_path):
    raw = write_raw(tmp_path, posting())
    run("seen.py", "mark", "--disposition", "killed",
        "--date", "2026-07-17", "--root", str(tmp_path), raw)
    r = run("seen.py", "mark", "--disposition", "shortlisted",
            "--date", "2026-07-18", "--root", str(tmp_path), raw)
    assert r.returncode == 0, r.stderr
    assert "nothing to mark" in r.stdout
    assert not (tmp_path / "state" / "seen" / "2026-07-18.jsonl").exists()


def test_check_unseen_exits_nonzero(tmp_path):
    raw = write_raw(tmp_path, posting())
    r = run("seen.py", "check", "--root", str(tmp_path), raw)
    assert r.returncode == 1
    assert "UNSEEN" in r.stdout


# ── audit ──────────────────────────────────────────────────────────────────


def _shortlist_entry(tmp_path, p, swept="2026-07-17"):
    d = tmp_path / "queue" / "shortlist" / p.slugify()
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.yaml").write_text(
        f"company: {p.company}\ntitle: {p.title}\nlocation: {p.location}\n"
        f"status: shortlisted\nswept: {swept}\n",
        encoding="utf-8",
    )


def test_audit_flags_swept_entry_missing_from_index(tmp_path):
    _shortlist_entry(tmp_path, posting())
    r = run("seen.py", "audit", "--root", str(tmp_path))
    assert r.returncode == 1
    assert "MISS" in r.stdout
    assert "re-triage" in r.stdout


def test_audit_passes_when_swept_entry_is_seen(tmp_path):
    p = posting()
    _shortlist_entry(tmp_path, p)
    raw = write_raw(tmp_path, p)
    run("seen.py", "mark", "--disposition", "shortlisted",
        "--date", "2026-07-17", "--root", str(tmp_path), raw)
    r = run("seen.py", "audit", "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_audit_ignores_manual_finds(tmp_path):
    # /add postings have no `swept:` and no structured triage — not sweepable,
    # so the audit must not demand seen records for them.
    d = tmp_path / "queue" / "ready" / "manual-role"
    d.mkdir(parents=True)
    (d / "meta.yaml").write_text(
        "company: Torrens\ntitle: Senior Director\nstatus: queued\n"
        "source: manual (LinkedIn)\ntriage: n/a (manual find)\n",
        encoding="utf-8",
    )
    r = run("seen.py", "audit", "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr


# ── audit: stored fingerprint beats recomputed meta text ───────────────────


def test_audit_prefers_meta_fingerprint_field(tmp_path):
    # Adapters often set company to the board slug ("acmelabs") while the
    # sweep writes the pretty name ("Acme Labs") into meta.yaml. With the
    # exact fingerprint stored in meta, the audit must still match.
    p = posting(company="acmelabs", title="Staff Engineer", location="Riverton")
    raw = write_raw(tmp_path, p)
    run("seen.py", "mark", "--disposition", "shortlisted",
        "--date", "2026-07-17", "--root", str(tmp_path), raw)
    d = tmp_path / "queue" / "shortlist" / "acme-labs-staff-engineer"
    d.mkdir(parents=True)
    (d / "meta.yaml").write_text(
        "company: Acme Labs\ntitle: Staff Engineer\nlocation: Riverton, Eastland\n"
        f"fingerprint: {p.fingerprint()}\nstatus: shortlisted\nswept: 2026-07-17\n",
        encoding="utf-8",
    )
    r = run("seen.py", "audit", "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


# ── mark from a meta.yaml (the repair path once raw JSONs are gone) ────────


def test_mark_accepts_meta_yaml_and_dirs(tmp_path):
    p = posting()
    d = tmp_path / "queue" / "shortlist" / p.slugify()
    d.mkdir(parents=True)
    (d / "meta.yaml").write_text(
        f"company: Pretty Name\ntitle: Anything\nfingerprint: {p.fingerprint()}\n"
        "status: shortlisted\nswept: 2026-07-17\n",
        encoding="utf-8",
    )
    r = run("seen.py", "mark", "--disposition", "shortlisted",
            "--date", "2026-07-17", "--root", str(tmp_path), str(d))
    assert r.returncode == 0, r.stderr
    shard = tmp_path / "state" / "seen" / "2026-07-17.jsonl"
    row = json.loads(shard.read_text().strip())
    assert row["fingerprint"] == p.fingerprint()
    # And the audit closes green.
    r = run("seen.py", "audit", "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr


# ── audit --date: seen-but-never-queued is LOST ────────────────────────────


def test_audit_date_flags_seen_but_never_queued(tmp_path):
    raw = write_raw(tmp_path, posting())
    run("seen.py", "mark", "--disposition", "shortlisted",
        "--date", "2026-07-17", "--root", str(tmp_path), raw)
    # No queue/shortlist entry was ever written — the crash-mid-sweep case.
    r = run("seen.py", "audit", "--date", "2026-07-17", "--root", str(tmp_path))
    assert r.returncode == 1
    assert "LOST" in r.stdout


def test_audit_date_ok_when_shortlist_exists(tmp_path):
    p = posting()
    raw = write_raw(tmp_path, p)
    _shortlist_entry(tmp_path, p)
    run("seen.py", "mark", "--disposition", "shortlisted",
        "--date", "2026-07-17", "--root", str(tmp_path), raw)
    r = run("seen.py", "audit", "--date", "2026-07-17", "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    # Killed rows need no queue entry — killing IS their terminal state.
    r = run("seen.py", "mark", "--disposition", "killed", "--date", "2026-07-17",
            "--root", str(tmp_path), write_raw(tmp_path, posting(title="Other"), "q.json"))
    assert r.returncode == 0
    r = run("seen.py", "audit", "--date", "2026-07-17", "--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr


# ── fetch.py: empty-index warning, and all-adapters-dead aborts loudly ─────


def test_fetch_warns_when_seen_index_empty(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "targets.yaml").write_text(
        "companies:\n  - ats: greenhouse\n    slug: nonexistent-board-xyz\n",
        encoding="utf-8",
    )
    r = run("fetch.py", "--dry-run", "--root", str(tmp_path))
    assert "seen index is empty" in r.stderr
    # The single (and thus every) adapter failed -> non-zero, so an unattended
    # sweep cannot mistake a broken environment for a quiet night.
    assert r.returncode == 2, r.stderr
    assert "all 1 adapter fetch(es) failed" in r.stderr
