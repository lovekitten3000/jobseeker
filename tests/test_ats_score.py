"""ats_score.py — the deterministic ATS keyword scorecard (PRD §21).

The number the tailor reports has to mean something, so these pin the parts a
model would otherwise fudge: which words count as keywords, which tier they
land in, and what counts as covered.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
FIX = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, BIN)

from ats_score import extract_keywords, load_ats_config, score, term_pattern  # noqa: E402

JD = open(os.path.join(FIX, "jd_sample.md"), encoding="utf-8").read()
CFG = load_ats_config(None)


def keywords(jd=JD, cfg=None):
    return {k["keyword"]: k for k in extract_keywords(jd, cfg or CFG)}


def run(script, *args):
    return subprocess.run(
        [sys.executable, os.path.join(BIN, script), *args], capture_output=True, text=True
    )


# ── extraction ─────────────────────────────────────────────────────────────


def test_repeated_requirement_outranks_a_passing_mention():
    ranked = [k["keyword"] for k in extract_keywords(JD, CFG)]
    assert "ci/cd" in ranked
    assert ranked.index("ci/cd") < ranked.index("kubernetes operations")


def test_tiers_follow_the_jd_s_own_headings():
    kw = keywords()
    assert kw["incident response"]["tier"] == "required"
    assert kw["kubernetes operations"]["tier"] == "preferred"


def test_boilerplate_and_function_words_are_not_keywords():
    kw = keywords()
    for junk in ("experience", "team", "opportunity", "candidate", "the team", "our customers"):
        assert junk not in kw, junk


def test_terms_never_cross_a_conjunction():
    # "Docker and container build systems" is two things an employer wants,
    # not one thing called "docker and container".
    kw = keywords()
    assert not [k for k in kw if " and " in k or " or " in k]


def test_nominal_connectors_survive_inside_a_term():
    assert "infrastructure as code" in keywords()


def test_a_fragment_that_never_stands_alone_is_folded_into_its_phrase():
    kw = keywords()
    assert "incident response" in kw
    assert "incident" not in kw


def test_extraction_is_deterministic():
    assert extract_keywords(JD, CFG) == extract_keywords(JD, CFG)


PLAIN_JD = """Registered Nurse

About the service
We care for residents across three wings.

Key selection criteria
- Demonstrated experience in medication management
- Wound care assessment and documentation

Desirable
- Palliative care experience

Responsibilities
Lead medication rounds. Escalate clinical deterioration.
"""


def test_a_bare_line_above_a_list_is_a_heading_not_content():
    # Postings pasted out of a portal have no markdown. "Key selection
    # criteria" tiers the block under it and contributes no keywords itself.
    kw = keywords(PLAIN_JD)
    assert kw["medication management"]["tier"] == "required"
    assert "key selection criteria" not in kw
    assert "selection criteria" not in kw


def test_a_duties_heading_ends_the_requirements_block():
    # Without this, "Responsibilities" sitting under "Desirable" would inherit
    # the preferred tier and mis-weight everything below it.
    kw = keywords(PLAIN_JD)
    assert kw["palliative care experience"]["tier"] == "preferred"
    assert kw["escalate clinical deterioration"]["tier"] == "body"


def test_a_trailing_full_stop_is_not_part_of_the_keyword():
    kw = keywords(PLAIN_JD)
    assert "escalate clinical deterioration" in kw
    assert not [k for k in kw if k.endswith(".")]


# ── coverage ───────────────────────────────────────────────────────────────


def test_coverage_tolerates_punctuation_plural_and_spelling():
    variant = {
        "skills": ["CI-CD"],
        "sections": [
            {
                "heading": "Experience",
                "bullets": [
                    {"text": "Ran incident responses for the platform team."},
                    {"text": "Drove cost optimization across the build estate."},
                ],
            }
        ],
    }
    rows = {r["keyword"]: r for r in score(JD, variant, None, CFG)["keywords"]}
    assert rows["ci/cd"]["in_resume"], "ci-cd in the skills list is the JD's ci/cd"
    assert rows["incident response"]["in_resume"], "a plural is the same keyword"
    assert rows["cost optimisation"]["in_resume"], "-ise and -ize are the same word"


def test_a_keyword_absent_from_the_draft_is_reported_missing():
    result = score(JD, {"sections": []}, None, CFG)
    assert result["overall"]["covered"] == 0
    assert "incident response" in result["missing_required"]


def test_repetition_past_the_cap_is_flagged_as_stuffing():
    bullets = [{"text": "Owned CI/CD."} for _ in range(6)]
    result = score(JD, {"sections": [{"heading": "X", "bullets": bullets}]}, None, CFG)
    assert "ci/cd" in result["overused"]


def test_the_cover_is_reported_separately_from_the_resume():
    variant = {"sections": [{"heading": "X", "bullets": [{"text": "Ran incident response."}]}]}
    rows = {r["keyword"]: r for r in score(JD, variant, "I lead incident response.", CFG)["keywords"]}
    assert rows["incident response"]["in_resume"]
    assert rows["incident response"]["in_cover"]
    assert rows["kubernetes operations"]["in_cover"] is False


def test_term_pattern_does_not_match_a_different_word():
    assert not term_pattern("power bi").search("powerful bill")


# ── cli ────────────────────────────────────────────────────────────────────


def test_cli_json_output(tmp_path):
    r = run(
        "ats_score.py",
        "--jd", os.path.join(FIX, "jd_sample.md"),
        "--variant", os.path.join(FIX, "variant_good.yaml"),
        "--config", str(tmp_path / "absent.yaml"),
        "--json",
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["overall"]["total"] > 0
    assert {"keyword", "tier", "in_resume"} <= set(data["keywords"][0])


def test_cli_reports_a_missing_file_instead_of_crashing(tmp_path):
    r = run("ats_score.py", "--jd", str(tmp_path / "nope.md"), "--variant", str(tmp_path / "n.yaml"))
    assert r.returncode == 2
    assert "no such file" in r.stderr
