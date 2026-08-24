#!/usr/bin/env python3
"""ats_score.py — deterministic ATS keyword coverage for one draft. PRD §21.

    ats_score.py --jd <jd.md> --variant <variant.yaml> [--cover <cover.md>]
                 [--config profile/config.yaml] [--top N] [--json]

Answers one question, the same way every time: **which of this posting's own
words appear in this draft, and which do not.** It reads the JD and the
already-written variant; it never writes, never scores fit, and never suggests
a claim.

Why it exists. The tailor used to self-report "n of m keywords covered", which
is a model grading its own homework — the number drifted with the draft's
confidence rather than its content. This computes it. The tailor runs it, acts
on the misses it can honestly act on, and reports the final number.

What the number is NOT. It is not a fit score (triage owns that, PRD §8.5) and
it is not permission to write anything. A keyword the evidence bank cannot
support is a **[SHORTFALL]**, stated plainly — never a bullet. Coverage rises
by finding real evidence that was left out, or by using the JD's word for work
the candidate genuinely did; never by claiming the thing.

Field-neutral by construction (PRD §20): no skills list, no role vocabulary, no
industry taxonomy. It knows English function words and hiring-document
boilerplate, and everything else it learns from the posting in front of it.
Every cue list is overridable under `ats:` in `profile/config.yaml`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

import yaml

# Section weights. A term in a requirements block matters more than the same
# term in the company's boilerplate about its mission.
TIER_WEIGHT = {"required": 3.0, "preferred": 2.0, "body": 1.0}
TIER_ORDER = ["required", "preferred", "body"]

# Headings that open a hard-requirements block. Hiring-document conventions,
# not industry vocabulary — and overridable (`ats.required_cues`).
DEFAULT_REQUIRED_CUES = [
    "requirement", "qualification", "must have", "must-have", "essential",
    "what you need", "what you'll need", "what you will need", "you have",
    "you will have", "you'll have", "who you are", "about you", "minimum",
    "we're looking for", "we are looking for", "skills and experience",
    "key selection criteria", "selection criteria",
]

# Headings that end a requirements block and go back to ordinary prose
# (`ats.body_cues`). Without these, a "Responsibilities" block sitting under
# "Desirable" would inherit the preferred tier and mis-weight the whole run.
DEFAULT_BODY_CUES = [
    "responsibilit", "duties", "what you'll do", "what you will do",
    "the role", "about", "day to day", "day-to-day", "benefit", "perks",
    "culture", "who we are", "our team", "how to apply", "salary",
    "package", "equal opportunity", "diversity",
]

# Headings that open a nice-to-have block (`ats.preferred_cues`).
DEFAULT_PREFERRED_CUES = [
    "preferred", "nice to have", "nice-to-have", "bonus", "desirable",
    "advantageous", "highly regarded", "well regarded", "a plus", "ideally",
    "even better", "pluses",
]

# English function words. Dropped as whole terms and never allowed to start or
# end an n-gram.
STOPWORDS = {
    "a", "about", "above", "across", "after", "against", "all", "also",
    "an", "and", "any", "are", "as", "at", "be", "been", "being", "below",
    "between", "both", "but", "by", "can", "could", "did", "do", "does",
    "doing", "down", "during", "each", "either", "etc", "even", "every", "few",
    "for", "from", "further", "had", "has", "have", "having", "he", "her",
    "here", "hers", "him", "his", "how", "however", "i", "if", "in", "into",
    "is", "it", "its", "itself", "just", "ll", "many", "may", "me", "might",
    "more", "most", "much", "must", "my", "no", "nor", "not", "of", "off",
    "on", "once", "one", "only", "or", "other", "our", "ours", "out", "over",
    "own", "per", "re", "same", "shall", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "us", "using", "ve", "very", "was", "we", "well", "were", "what", "when",
    "where", "whether", "which", "while", "who", "whom", "why", "will", "with",
    "within", "would", "you", "your", "yours",
}

# Words every posting says about every job. Useless as keywords on their own;
# still allowed *inside* a longer term ("stakeholder management" survives,
# "management" alone does not). Extend, don't replace, via
# `ats.extra_boilerplate`.
BOILERPLATE = {
    "ability", "able", "applicant", "application", "apply", "background",
    "benefit", "benefits", "candidate", "candidates", "career", "colleague",
    "colleagues", "company", "culture", "day", "days", "duties", "employee",
    "employees", "employer", "environment", "excellent", "experience",
    "experienced", "great", "group", "help", "hiring", "hour", "hours", "job",
    "join", "level", "look", "looking", "month", "months", "need", "needs",
    "new", "office", "opportunity", "organisation", "organization", "part",
    "pay", "people", "person", "position", "provide", "responsibilities",
    "responsibility", "role", "roles", "salary", "senior", "skill", "skills",
    "staff", "strong", "successful", "support", "team", "teams", "time",
    "understanding", "vacancy", "week", "weeks", "work", "working", "year",
    "years",
}

WORD = re.compile(r"[a-z0-9][a-z0-9+#./-]*")
MD_NOISE = re.compile(r"<[^>]+>|[*_`>#]|\[|\]|\(|\)")
# Clause boundaries. A term must sit inside one clause, or a list line like
# "deploy time and developer experience" invents "time and developer".
CLAUSE_SPLIT = re.compile(r"[,;:•|]|\.(?=\s|$)|\s[–—-]\s")
# Function words allowed *inside* a term, because real terms use them
# ("infrastructure as code", "return on investment"). Everything else in
# STOPWORDS breaks a term in two.
INNER_STOPWORDS = {"as", "of", "on"}
NUMERIC = re.compile(r"^\d+[+]?$")


def load_ats_config(path: str | None) -> dict:
    """Read the optional `ats:` block from config.yaml. Absent = defaults."""
    cfg: dict = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if isinstance(data, dict) and isinstance(data.get("ats"), dict):
            cfg = data["ats"]
    return {
        "top_keywords": int(cfg.get("top_keywords", 25) or 25),
        "max_repeats": int(cfg.get("max_repeats", 4) or 4),
        "required_cues": [str(c).lower() for c in cfg.get("required_cues") or DEFAULT_REQUIRED_CUES],
        "preferred_cues": [
            str(c).lower() for c in cfg.get("preferred_cues") or DEFAULT_PREFERRED_CUES
        ],
        "body_cues": [str(c).lower() for c in cfg.get("body_cues") or DEFAULT_BODY_CUES],
        "boilerplate": BOILERPLATE | {str(w).lower() for w in cfg.get("extra_boilerplate") or []},
    }


LIST_MARKER = re.compile(r"^\s*([-*•·‣]|\d+[.)])\s")


def _is_heading(raw: str, text: str, next_raw: str, cfg: dict) -> bool:
    """Does this line introduce a block rather than carry content?

    Postings arrive as markdown, as HTML stripped to text, and as plain text
    pasted out of a portal, so all three shapes have to be recognised: a
    markdown or bolded heading, a line ending in a colon, an ALL-CAPS line,
    and — the one that matters most in practice — a bare short line like
    "Key selection criteria" with the requirements listed under it.

    The bare case is the risky one: a short prose line without a full stop
    looks identical. So it counts as a heading only when something corroborates
    it — the next line is a list item, or the line itself names a tier.
    """
    s = raw.strip()
    if not text or len(text) > 70:
        return False
    if s.startswith("#") or (s.startswith("**") and s.endswith("**")):
        return True
    if LIST_MARKER.match(raw):
        return False
    if text.endswith(":"):
        return True
    letters = [c for c in text if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return True
    if len(text.split()) <= 6 and text[-1] not in ".!?,;":
        return bool(LIST_MARKER.match(next_raw)) or _tier_for_heading(text, cfg) is not None
    return False


def _tier_for_heading(heading: str, cfg: dict) -> str | None:
    """The tier a heading opens, or None when it names no tier at all.

    Required beats preferred beats body, so "Essential and desirable criteria"
    reads as essential rather than as a nice-to-have.
    """
    h = heading.lower()
    if any(cue in h for cue in cfg["required_cues"]):
        return "required"
    if any(cue in h for cue in cfg["preferred_cues"]):
        return "preferred"
    if any(cue in h for cue in cfg["body_cues"]):
        return "body"
    return None


def split_sections(jd_text: str, cfg: dict) -> list[tuple[str, str]]:
    """Return [(tier, line)] for every *content* line in the JD.

    A heading sets the tier for the lines under it and contributes no terms of
    its own — "Key selection criteria" is structure, not something the employer
    wants you to have done. Text before any recognised heading is `body`. An
    inline cue on a content line ("Nice to have: X") tiers that line alone.
    """
    raw_lines = jd_text.splitlines()
    cleaned = [MD_NOISE.sub(" ", ln).strip() for ln in raw_lines]
    out: list[tuple[str, str]] = []
    tier = "body"
    for i, line in enumerate(cleaned):
        if not line:
            continue
        next_raw = next((raw_lines[j] for j in range(i + 1, len(cleaned)) if cleaned[j]), "")
        if _is_heading(raw_lines[i], line, next_raw, cfg):
            tier = _tier_for_heading(line, cfg) or "body"
            continue
        inline = _tier_for_heading(line.split(":", 1)[0], cfg) if ":" in line else None
        out.append((inline or tier, line))
    return out


def _clauses(line: str) -> list[list[str]]:
    """One line to its clauses, each as a token list."""
    return [WORD.findall(part.lower()) for part in CLAUSE_SPLIT.split(line) if part.strip()]


def _terms(line: str, boilerplate: set[str], max_n: int = 3) -> list[str]:
    """Every 1..max_n-gram in `line` worth counting.

    A term is dropped when it starts or ends with a function word, when a
    function word other than a nominal connector sits inside it ("docker and
    container" is two terms, not one), when it opens with a bare number, and
    when every token in it is filler. So "stakeholder management" and
    "infrastructure as code" survive; "management", "of the team", and
    "5+ years building" do not.
    """
    out: list[str] = []
    for tokens in _clauses(line):
        for n in range(1, max_n + 1):
            for i in range(len(tokens) - n + 1):
                gram = tokens[i : i + n]
                if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                    continue
                if any(t in STOPWORDS and t not in INNER_STOPWORDS for t in gram[1:-1]):
                    continue
                if NUMERIC.match(gram[0]):
                    continue
                if all(t in STOPWORDS or t in boilerplate or NUMERIC.match(t) for t in gram):
                    continue
                if any(len(t) < 2 for t in gram):
                    continue
                out.append(" ".join(gram))
    return out


def extract_keywords(jd_text: str, cfg: dict) -> list[dict]:
    """Rank the posting's own terms. Deterministic: same JD, same list.

    Weight is frequency times where it appears — a term in the requirements
    block outranks the same term in the culture paragraph. Repetition is the
    signal: what an employer says three times is what they are buying.
    """
    counts: dict[str, int] = defaultdict(int)
    weighted: dict[str, float] = defaultdict(float)
    tier_mass: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for tier, line in split_sections(jd_text, cfg):
        for term in _terms(line, cfg["boilerplate"]):
            counts[term] += 1
            weighted[term] += TIER_WEIGHT[tier]
            tier_mass[term][tier] += TIER_WEIGHT[tier]

    # Collapse fragments: a term that never occurs outside a longer term is
    # that longer term ("incident" inside "incident response"). Keep the one
    # the employer actually wrote.
    subsumed = {
        short
        for short in counts
        for long in counts
        if long != short and _contains_term(long, short) and counts[long] >= counts[short]
    }
    ranked = sorted(
        (t for t in counts if t not in subsumed),
        key=lambda t: (-weighted[t], -len(t.split()), t),
    )

    selected: list[dict] = []
    for term in ranked:
        if len(selected) >= cfg["top_keywords"]:
            break
        mass = tier_mass[term]
        tier = min(
            (t for t in TIER_ORDER if mass.get(t)),
            key=lambda t: (-mass[t], TIER_ORDER.index(t)),
            default="body",
        )
        selected.append(
            {"keyword": term, "tier": tier, "jd_count": counts[term], "weight": weighted[term]}
        )
    return selected


def _contains_term(haystack: str, needle: str) -> bool:
    """True when `needle`'s words appear as a run inside `haystack`."""
    h, n = haystack.split(), needle.split()
    return any(h[i : i + len(n)] == n for i in range(len(h) - len(n) + 1))


TOKEN_SPLIT = re.compile(r"[\s/._-]+")


def term_pattern(term: str) -> re.Pattern:
    """Match a term tolerantly: plural, punctuation, spelling variant.

    "ci/cd" matches "CI-CD" and "ci cd"; "incident response" matches
    "Incident-Response" and "incident responses"; "optimisation" matches
    "optimization", because which spelling a posting uses says nothing about
    whether the candidate did the work. It does not match "responses to
    incidents" — tolerance stops where a match would stop being the same word.
    """
    parts = []
    for tok in TOKEN_SPLIT.split(term):
        if not tok:
            continue
        # -ise/-isation and -ize/-ization are the same word.
        parts.append(re.sub(r"i[sz](?=[ea])", "i[sz]", re.escape(tok)))
    parts[-1] = parts[-1] + r"(?:e?s)?"
    return re.compile(
        r"(?<![a-z0-9])" + r"[\s\-/_.]*".join(parts) + r"(?![a-z0-9])", re.IGNORECASE
    )


def variant_text(variant: dict) -> str:
    """Every human-readable string in the variant, flattened."""
    parts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif node is not None:
            parts.append(str(node))

    walk(variant)
    return "\n".join(parts)


def score(
    jd_text: str, variant: dict, cover_text: str | None, cfg: dict
) -> dict:
    keywords = extract_keywords(jd_text, cfg)
    rtext = variant_text(variant)
    ctext = cover_text or ""

    rows = []
    for kw in keywords:
        pat = term_pattern(kw["keyword"])
        hits = pat.findall(rtext)
        rows.append(
            {
                **{k: kw[k] for k in ("keyword", "tier", "jd_count")},
                "in_resume": bool(hits),
                "resume_count": len(hits),
                "in_cover": bool(pat.search(ctext)) if cover_text is not None else None,
            }
        )

    def tally(tier: str) -> dict:
        subset = [r for r in rows if r["tier"] == tier]
        return {"covered": sum(1 for r in subset if r["in_resume"]), "total": len(subset)}

    overused = sorted(
        r["keyword"] for r in rows if r["resume_count"] > cfg["max_repeats"]
    )
    return {
        "keywords": rows,
        "required": tally("required"),
        "preferred": tally("preferred"),
        "body": tally("body"),
        "overall": {
            "covered": sum(1 for r in rows if r["in_resume"]),
            "total": len(rows),
        },
        "missing_required": [r["keyword"] for r in rows if r["tier"] == "required" and not r["in_resume"]],
        "missing_preferred": [
            r["keyword"] for r in rows if r["tier"] == "preferred" and not r["in_resume"]
        ],
        "missing_body": [r["keyword"] for r in rows if r["tier"] == "body" and not r["in_resume"]],
        "overused": overused,
        "max_repeats": cfg["max_repeats"],
    }


def render(result: dict, jd_path: str, with_cover: bool) -> str:
    lines = [f"ATS scorecard — {jd_path}", ""]
    for tier in TIER_ORDER:
        t = result[tier]
        if t["total"]:
            lines.append(f"  {tier:<10} {t['covered']}/{t['total']}")
    o = result["overall"]
    lines.append(f"  {'overall':<10} {o['covered']}/{o['total']}")
    lines.append("")
    head = f"  {'tier':<10} {'keyword':<34} {'jd':>3}  resume"
    lines.append(head + ("  cover" if with_cover else ""))
    for r in result["keywords"]:
        row = (
            f"  {r['tier']:<10} {r['keyword'][:34]:<34} {r['jd_count']:>3}  "
            f"{'yes' if r['in_resume'] else 'NO ':<6}"
        )
        if with_cover:
            row += f"  {'yes' if r['in_cover'] else 'no'}"
        lines.append(row.rstrip())
    for label, key in (
        ("MISSING (required)", "missing_required"),
        ("missing (preferred)", "missing_preferred"),
    ):
        if result[key]:
            lines += ["", f"  {label}: {', '.join(result[key])}"]
    if result["overused"]:
        lines += [
            "",
            f"  over-used (>{result['max_repeats']}x in the resume — reads as stuffing "
            f"to a human): {', '.join(result['overused'])}",
        ]
    lines += [
        "",
        "  A miss is not an instruction. Cover it only from evidence that already",
        "  exists; otherwise it is a [SHORTFALL], stated plainly.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic ATS keyword coverage for a tailored draft."
    )
    parser.add_argument("--jd", required=True, help="the posting (jd.md or plain text)")
    parser.add_argument("--variant", required=True, help="the tailored variant.yaml")
    parser.add_argument("--cover", help="optional cover.md, reported alongside")
    parser.add_argument("--config", default="profile/config.yaml", help="config.yaml with `ats:`")
    parser.add_argument("--top", type=int, help="how many keywords to score (default 25)")
    parser.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    args = parser.parse_args(argv)

    for path in (args.jd, args.variant):
        if not os.path.exists(path):
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2

    cfg = load_ats_config(args.config)
    if args.top:
        cfg["top_keywords"] = args.top

    with open(args.jd, encoding="utf-8") as fh:
        jd_text = fh.read()
    with open(args.variant, encoding="utf-8") as fh:
        variant = yaml.safe_load(fh) or {}
    if not isinstance(variant, dict):
        print(f"error: {args.variant} is not a mapping", file=sys.stderr)
        return 2
    cover_text = None
    if args.cover:
        if not os.path.exists(args.cover):
            print(f"error: no such file: {args.cover}", file=sys.stderr)
            return 2
        with open(args.cover, encoding="utf-8") as fh:
            cover_text = fh.read()

    result = score(jd_text, variant, cover_text, cfg)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result, args.jd, cover_text is not None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
