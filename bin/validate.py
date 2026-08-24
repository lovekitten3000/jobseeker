#!/usr/bin/env python3
"""validate.py — the provenance gate. PRD §8.3, principle 3.4, red lines §10.

    validate.py <variant.yaml> [--bank profile/evidence-bank.md] [--resume profile/resume.yaml]
    validate.py --cover <cover.md> --variant <variant.yaml> [--bank ...] [--note ...]
    validate.py --lint-bank [--bank profile/evidence-bank.md]

Deterministic. Regex-able. No model in the gate. Exits non-zero on any
violation, printing every violation found (not just the first).

This catches invention: a bullet with no evidence ID, a metric that traces to
an estimate, a technology with no backing. It does NOT catch *stretching* — a
bullet that cites ev:0031 but overstates what ev:0031 says. That is Gate 2's
job. See PRD §1/G6. Do not trust the green check to mean more than it does.

It also enforces the style gate (PRD §14): banned substrings — em dashes and
stock AI phrasing — fail resume bullets and covers. The list lives in
`profile/config.yaml` under `style.banned`; without a config the built-in
defaults apply. Deterministic, like everything else here.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

# ── evidence bank parsing ──────────────────────────────────────────────────

EV_HEADER = re.compile(r"^###\s+(ev:\d+)\b", re.MULTILINE)
FIELD = re.compile(r"^([a-z_]+):\s*(.*)$")


def parse_bank(path: str) -> dict[str, dict]:
    """Parse evidence-bank.md into {ev_id: {confidence, tags, metric, ...}}.

    Entries are `### ev:NNNN` headers followed by `field: value` lines up to
    the next header. Free-form narrative blocks are ignored for gating.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    entries: dict[str, dict] = {}
    headers = list(EV_HEADER.finditer(text))
    for i, m in enumerate(headers):
        ev_id = m.group(1)
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        fields: dict[str, str] = {}
        for line in block.splitlines():
            fm = FIELD.match(line.strip())
            if fm:
                fields[fm.group(1)] = fm.group(2).strip()
        tags = [t.strip().lower() for t in fields.get("tags", "").split(",") if t.strip()]
        entries[ev_id] = {
            "confidence": fields.get("confidence", "").strip().lower(),
            "tags": tags,
            "raw": fields,
        }
    return entries


def bank_tags(entries: dict[str, dict]) -> set[str]:
    tags: set[str] = set()
    for e in entries.values():
        tags.update(e["tags"])
    return tags


def entry_angles(entries: dict[str, dict]) -> dict[str, list[str]]:
    """{ev_id: [angle slug, ...]} from each entry's `angles:` field."""
    out: dict[str, list[str]] = {}
    for ev, e in entries.items():
        raw = e["raw"].get("angles", "")
        out[ev] = [a.strip().lower() for a in raw.split(",") if a.strip()]
    return out


# ── angle parsing (PRD §21) ────────────────────────────────────────────────

ANGLE_HEADER = re.compile(
    r"^###\s+angle:\s*([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE | re.IGNORECASE
)
LEGACY_ANGLE = re.compile(
    r"^[-*]\s+`([a-z0-9][a-z0-9-]*)`\s*[—-]\s*(.+)$", re.MULTILINE | re.IGNORECASE
)
EV_REF = re.compile(r"ev:\d+")


def parse_angles(path: str) -> dict[str, dict]:
    """Parse the bank's `## Angles` block into {slug: {claim, proof, serves}}.

    An angle is a positioning stance: one claim, proved by evidence, aimed at a
    track (PRD §21). The current shape is a block per angle —

        ### angle: the-slug
        claim:  one line, in the candidate's own words
        proof:  ev:0031, ev:0044
        serves: <track ids from goals.yaml>

    — and the original one-bullet shape (`- \`slug\` — claim`) still parses, so
    a bank written before §21 keeps working. A legacy angle carries no proof,
    which `--lint-bank` reports: an angle nothing proves is a slogan.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    angles: dict[str, dict] = {}
    headers = list(ANGLE_HEADER.finditer(text))
    for i, m in enumerate(headers):
        slug = m.group(1).lower()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[m.end() : end]
        # Stop at the next top-level section, so `## Evidence` is not read in.
        block = re.split(r"^##\s", block, maxsplit=1, flags=re.MULTILINE)[0]
        fields: dict[str, str] = {}
        for line in block.splitlines():
            fm = FIELD.match(line.strip())
            if fm:
                fields[fm.group(1)] = fm.group(2).strip()
        angles[slug] = {
            "claim": fields.get("claim", "").strip(),
            "proof": EV_REF.findall(fields.get("proof", "")),
            "serves": [s.strip() for s in fields.get("serves", "").split(",") if s.strip()],
            "legacy": False,
        }

    for m in LEGACY_ANGLE.finditer(text):
        slug = m.group(1).lower()
        angles.setdefault(
            slug, {"claim": m.group(2).strip(), "proof": [], "serves": [], "legacy": True}
        )
    return angles


def variant_angle(variant: dict) -> str:
    """The angle a variant declares, under either accepted key.

    `angle:` is the current key; `label:` is what early variants called the
    same thing.
    """
    for key in ("angle", "label"):
        value = variant.get(key)
        if value and str(value).strip():
            return str(value).strip().lower()
    return ""


def lint_bank(bank_path: str) -> list[str]:
    """Check the bank's angles hold together. PRD §21.

    Deterministic, like everything else in this file, and the same boundary
    applies: it catches an angle that does not exist or that nothing proves.
    Whether an angle is a *good* pitch is a human judgment.
    """
    if not os.path.exists(bank_path):
        return [f"evidence bank not found: {bank_path}"]
    errors: list[str] = []
    entries = parse_bank(bank_path)
    angles = parse_angles(bank_path)

    if not angles:
        errors.append("bank declares no `## Angles`; every variant is then unpositioned")

    for ev, slugs in entry_angles(entries).items():
        for slug in slugs:
            if slug not in angles:
                errors.append(f"{ev} claims angle {slug!r} which is not declared in `## Angles`")

    for slug, angle in sorted(angles.items()):
        if not angle["claim"]:
            errors.append(f"angle {slug!r} has no claim line")
        for ev in angle["proof"]:
            if ev not in entries:
                errors.append(f"angle {slug!r} cites {ev} which is not in the bank")
        proven_by = [ev for ev, s in entry_angles(entries).items() if slug in s]
        support = set(angle["proof"]) | set(proven_by)
        if len(support) < 2:
            errors.append(
                f"angle {slug!r} rests on {len(support)} evidence entr(y/ies); an angle "
                f"two entries cannot prove is a slogan (add `proof:` or tag more entries)"
            )
    return errors


# ── style gate ─────────────────────────────────────────────────────────────

# Applied when profile/config.yaml has no style.banned list. Case-insensitive
# substring match. "leverag" covers leverage/leveraging; "delve" covers delved;
# "unlock" covers unlocking/unlocked.
DEFAULT_BANNED = [
    "—",
    "I am writing to apply",
    "excited to apply",
    "thrilled",
    "delve",
    "spearhead",
    "leverag",
    "seamless",
    "cutting-edge",
    "fast-paced",
    "proven track record",
    "passionate about",
    "not just",
    "not only",
    "not merely",
    "not simply",
    "tapestry",
    "unlock",
    "paramount",
    "furthermore",
    "moreover",
    "symphony",
    "testament",
    "game-chang",
    "in today's",
    "here's the truth",
    "what nobody tells you",
    "at the end of the day",
    "in conclusion",
]

# Case-insensitive regexes for structures a substring can't catch — chiefly the
# "It's not X, it's Y" negation cliché in its common spellings.
DEFAULT_BANNED_REGEX = [
    r"\bit'?s not [^.!?\n]{1,60}?[,;.] ?it'?s\b",
    r"\bisn'?t [^.!?\n]{1,60}?[,;.] ?it'?s\b",
]


def load_banned(config_path: str | None) -> tuple[list[str], list[str]]:
    """Return (banned substrings, banned regexes) from config, else defaults."""
    banned = list(DEFAULT_BANNED)
    banned_regex = list(DEFAULT_BANNED_REGEX)
    if config_path and os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        style = cfg.get("style") or {}
        if isinstance(style.get("banned"), list) and style["banned"]:
            banned = [str(b) for b in style["banned"]]
        if isinstance(style.get("banned_regex"), list) and style["banned_regex"]:
            banned_regex = [str(b) for b in style["banned_regex"]]
    return banned, banned_regex


def style_errors(
    text: str, banned: list[str], where: str, banned_regex: list[str] | None = None
) -> list[str]:
    errors: list[str] = []
    lowered = text.lower()
    for pat in banned:
        idx = lowered.find(pat.lower())
        if idx != -1:
            context = text[max(0, idx - 25) : idx + len(pat) + 25].replace("\n", " ").strip()
            errors.append(f"[{where}] banned style pattern {pat!r}: …{context}…")
    for pat in banned_regex or []:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            context = text[max(0, m.start() - 25) : m.end() + 25].replace("\n", " ").strip()
            errors.append(f"[{where}] banned style regex {pat!r}: …{context}…")
    return errors


# ── numeral / metric detection ─────────────────────────────────────────────

NUMERAL = re.compile(r"\d+(?:[.,]\d+)?")
# A hedge makes a number directional rather than a hard claim.
HEDGE = re.compile(
    r"(~|≈|about|around|roughly|approximately|approx\.?|est\.?|estimated|"
    r"nearly|almost|over|under|up to|order of)",
    re.IGNORECASE,
)


def numerals(text: str) -> list[str]:
    """Digit sequences in `text`, normalized (commas stripped)."""
    return [n.replace(",", "") for n in NUMERAL.findall(text)]


def has_hard_metric(text: str) -> bool:
    """True if `text` contains a number NOT softened by a nearby hedge word.

    We check a small window before each numeral for a hedge. This is the
    "measured may appear as a hard metric; estimated may be directional only"
    rule from PRD §8.0.
    """
    for m in NUMERAL.finditer(text):
        window = text[max(0, m.start() - 20) : m.start()]
        if not HEDGE.search(window):
            return True
    return False


# ── variant flattening ─────────────────────────────────────────────────────


def flatten_bullets(variant: dict) -> list[tuple[str, dict]]:
    """Yield (context_label, bullet_dict) for every bullet in the variant.

    A bullet is {text, ev}. Bullets live directly under a section, or under an
    entry within a section.
    """
    out: list[tuple[str, dict]] = []
    for section in variant.get("sections", []) or []:
        heading = section.get("heading", "?")
        for bullet in section.get("bullets", []) or []:
            out.append((heading, bullet))
        for entry in section.get("entries", []) or []:
            label = f"{heading}/{entry.get('company', '?')}"
            for bullet in entry.get("bullets", []) or []:
                out.append((label, bullet))
    return out


def claimed_skills(variant: dict) -> list[str]:
    """The variant's skills list, under either accepted key.

    `technologies:` is the original key and still works. `skills:` is the
    field-neutral synonym — a nurse's variant lists clinical competencies, a
    teacher's lists curricula, and neither is a technology (PRD §19). Both may
    be present; the union is what gets gated.
    """
    out: list[str] = []
    for key in ("skills", "technologies"):
        for item in variant.get(key, []) or []:
            if str(item).strip() and str(item) not in out:
                out.append(str(item))
    return out


def canonical_employers(variant: dict) -> list[dict]:
    out: list[dict] = []
    for section in variant.get("sections", []) or []:
        for entry in section.get("entries", []) or []:
            if "company" in entry and "title" in entry:
                out.append(entry)
    return out


# ── resume mode ────────────────────────────────────────────────────────────


def validate_resume(
    variant_path: str,
    bank_path: str,
    resume_path: str | None,
    banned: list[str] | None = None,
    banned_regex: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    banned = banned if banned is not None else list(DEFAULT_BANNED)
    banned_regex = banned_regex if banned_regex is not None else list(DEFAULT_BANNED_REGEX)
    with open(variant_path, encoding="utf-8") as fh:
        variant = yaml.safe_load(fh) or {}

    if not os.path.exists(bank_path):
        return [f"evidence bank not found: {bank_path}"]
    bank = parse_bank(bank_path)
    tags = bank_tags(bank)

    # Every bullet must cite an ev that exists; its metrics must be supported.
    for label, bullet in flatten_bullets(variant):
        text = str(bullet.get("text", "")).strip()
        ev = str(bullet.get("ev", "")).strip()
        snippet = text[:60]
        errors.extend(style_errors(text, banned, label, banned_regex))
        # Resume bullets lead with the action; no "Label: detail" structures
        # (requested 2026-07-18). Covers may still use colons in prose.
        if ": " in text:
            errors.append(
                f"[{label}] bullet uses a colon-led structure; lead with the "
                f"action and weave the detail in: {snippet!r}"
            )
        if not ev:
            errors.append(f"[{label}] bullet has no evidence ID: {snippet!r}")
            continue
        if ev not in bank:
            errors.append(f"[{label}] cites {ev} which is not in the bank: {snippet!r}")
            continue
        confidence = bank[ev]["confidence"]
        nums = numerals(text)
        if confidence == "qualitative" and nums:
            errors.append(
                f"[{label}] {ev} is qualitative but bullet asserts a numeral "
                f"({', '.join(nums)}): {snippet!r}"
            )
        elif confidence == "estimated" and has_hard_metric(text):
            errors.append(
                f"[{label}] {ev} is estimated but bullet states a hard metric "
                f"(use directional phrasing): {snippet!r}"
            )

    # A declared angle must exist in the bank. The angle is what the resume
    # argues; an argument the bank never makes is invention like any other
    # (PRD §21). Silent when the variant declares none, or the bank predates
    # angles entirely.
    angle = variant_angle(variant)
    if angle:
        angles = parse_angles(bank_path)
        if angles and angle not in angles:
            errors.append(
                f"variant is positioned on angle {angle!r} which the bank does not declare "
                f"(declared: {', '.join(sorted(angles)) or 'none'})"
            )

    # A skill in the skills list must be tagged by some evidence entry.
    for skill in claimed_skills(variant):
        if skill.strip().lower() not in tags:
            errors.append(f"skill {skill!r} is claimed but no evidence entry tags it")

    # Canonical facts must match resume.yaml if present.
    if resume_path and os.path.exists(resume_path):
        with open(resume_path, encoding="utf-8") as fh:
            resume = yaml.safe_load(fh) or {}
        canon = {
            (e.get("company"), e.get("title"), str(e.get("dates")))
            for e in resume.get("employers", []) or []
        }
        for entry in canonical_employers(variant):
            key = (entry.get("company"), entry.get("title"), str(entry.get("dates")))
            if key not in canon:
                errors.append(
                    f"experience {key} diverges from canonical resume.yaml "
                    f"(employer/title/dates must match exactly)"
                )

    return errors


# ── cover mode ─────────────────────────────────────────────────────────────


def _variant_text(variant: dict) -> str:
    """All human-readable strings in the variant, flattened for substring search."""
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


def validate_cover(
    cover_path: str,
    variant_path: str,
    bank_path: str,
    note_path: str | None,
    banned: list[str] | None = None,
    banned_regex: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    banned = banned if banned is not None else list(DEFAULT_BANNED)
    banned_regex = banned_regex if banned_regex is not None else list(DEFAULT_BANNED_REGEX)
    with open(cover_path, encoding="utf-8") as fh:
        cover = fh.read()
    errors.extend(style_errors(cover, banned, "cover", banned_regex))
    with open(variant_path, encoding="utf-8") as fh:
        variant = yaml.safe_load(fh) or {}

    vtext = _variant_text(variant)
    variant_nums = set(numerals(vtext))

    # Numerals from the company note (the hook) are also allowed — they are
    # claims about the company, not about the candidate. PRD §4.3, §8.6.
    allowed_nums = set(variant_nums)
    if note_path and os.path.exists(note_path):
        with open(note_path, encoding="utf-8") as fh:
            allowed_nums |= set(numerals(fh.read()))

    for n in numerals(cover):
        if n not in allowed_nums:
            errors.append(
                f"cover asserts numeral {n!r} that is absent from the validated variant "
                f"(a metric in the letter must trace to the resume)"
            )

    # Employer names present in the variant define the allowed employer vocab.
    variant_companies = {
        str(e.get("company", "")).strip()
        for e in canonical_employers(variant)
        if e.get("company")
    }
    # Any *other* known employer (from the bank's role: fields) mentioned in the
    # cover but not in the variant is a fabricated affiliation.
    if os.path.exists(bank_path):
        bank = parse_bank(bank_path)
        known_employers: set[str] = set()
        for e in bank.values():
            role = e["raw"].get("role", "")
            if "," in role:
                known_employers.add(role.split(",", 1)[1].strip())
        for emp in known_employers - variant_companies:
            if emp and re.search(rf"\b{re.escape(emp)}\b", cover):
                errors.append(
                    f"cover mentions employer {emp!r} that is not in the validated variant"
                )

        # Skills mentioned in the cover must be in the variant.
        for skill in bank_tags(bank):
            if len(skill) < 3:
                continue
            if re.search(rf"\b{re.escape(skill)}\b", cover, re.IGNORECASE) and not re.search(
                rf"\b{re.escape(skill)}\b", vtext, re.IGNORECASE
            ):
                errors.append(
                    f"cover mentions skill {skill!r} that is not in the validated variant"
                )

    return errors


# ── cli ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provenance gate for resumes and covers.")
    parser.add_argument("variant", nargs="?", help="path to variant.yaml (resume mode)")
    parser.add_argument("--cover", help="path to cover.md (cover mode)")
    parser.add_argument("--variant", dest="variant_flag", help="variant.yaml for cover mode")
    parser.add_argument("--bank", default="profile/evidence-bank.md")
    parser.add_argument("--resume", default="profile/resume.yaml")
    parser.add_argument("--note", help="optional company note whose numerals are also allowed")
    parser.add_argument(
        "--lint-bank",
        action="store_true",
        help="check the bank's `## Angles` block instead of a draft (PRD §21)",
    )
    parser.add_argument(
        "--config",
        default="profile/config.yaml",
        help="config.yaml providing style.banned; built-in defaults if absent",
    )
    args = parser.parse_args(argv)

    banned, banned_regex = load_banned(args.config)

    if args.lint_bank:
        errors = lint_bank(args.bank)
        mode = f"bank {args.bank}"
    elif args.cover:
        variant_path = args.variant_flag or args.variant
        if not variant_path:
            parser.error("--cover requires --variant")
        errors = validate_cover(
            args.cover, variant_path, args.bank, args.note, banned, banned_regex
        )
        mode = f"cover {args.cover}"
    else:
        if not args.variant:
            parser.error("a variant.yaml path is required")
        errors = validate_resume(args.variant, args.bank, args.resume, banned, banned_regex)
        mode = f"resume {args.variant}"

    if errors:
        print(f"FAIL: {mode} — {len(errors)} violation(s):", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        return 1
    print(
        f"OK: {mode} — {'angles hold' if args.lint_bank else 'provenance clean'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
