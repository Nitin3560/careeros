import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.candidate_evidence import (  # noqa: E402
    compute_professional_swe_years,
    load_attested_facts,
)
from app.services.skill_ontology import expanded_profile_terms, requirement_terms  # noqa: E402

DEFAULT_USER_ID = "b57ae27a-e0b1-4ceb-bab0-3010778465b2"
REVIEW_TYPES = {"citizenship", "clearance", "authorization", "residency"}
CONSEQUENTIAL_TYPES = {"citizenship", "clearance", "authorization", "residency", "location", "education"}
YEARS_STRETCH_MIN = 3
YEARS_SKIP_MIN = 5
BROAD_SKILL_TERMS = {
    "ability",
    "capability",
    "communication",
    "collaborative",
    "comfort with ambiguity",
    "fundamentals",
    "ownership",
    "problem solving",
    "shipping a product",
    "software design",
}


@dataclass
class Decision:
    action: str
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    years_min: int | None = None
    candidate_years: float = 0.0


def norm(value) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", str(value or "").lower()).strip()


def load_profile(user_id: str) -> dict:
    db = SessionLocal()
    try:
        return db.execute(
            text("SELECT data FROM candidate_profiles WHERE user_id::text = :user_id"),
            {"user_id": user_id},
        ).scalar_one()
    finally:
        db.close()


def profile_facts(profile: dict, attested: dict | None = None, years: float | None = None) -> dict:
    skills = {
        norm(skill.get("name"))
        for skill in profile.get("skills", [])
        if isinstance(skill, dict) and skill.get("name")
    }
    expanded_skills = expanded_profile_terms(skills)
    text_parts = []
    for skill in profile.get("skills", []):
        if isinstance(skill, dict):
            text_parts.append(skill.get("name", ""))
            text_parts.extend(skill.get("evidence", []))
    for role in profile.get("preferred_roles", []):
        text_parts.append(role)
    for exp in profile.get("experience", []):
        if isinstance(exp, dict):
            text_parts.extend([exp.get("title", ""), exp.get("company", "")])
            text_parts.extend(exp.get("highlights", []))
    for edu in profile.get("education", []):
        if isinstance(edu, dict):
            text_parts.extend([edu.get("degree", ""), edu.get("institution", "")])
    return {
        "skills": skills,
        "expanded_skills": expanded_skills,
        "text": norm(" ".join(text_parts)),
        "years": years if years is not None else estimate_years(profile),
        "attested": attested if attested is not None else profile.get("attested", {}),
    }


def estimate_years(profile: dict) -> float:
    years = 0.0
    for exp in profile.get("experience", []):
        duration = exp.get("duration", "") if isinstance(exp, dict) else ""
        found = [int(value) for value in re.findall(r"\b(20\d{2})\b", duration)]
        if len(found) >= 2:
            years += max(found) - min(found)
        elif len(found) == 1:
            years += 1
    return years


def requirement_label(req: dict) -> str:
    return req.get("value") or req.get("skill") or req.get("source_text") or ""


def has_fact(facts: dict, req: dict) -> bool:
    req_type = req.get("type")
    value = norm(req.get("skill") or req.get("value"))
    source = norm(req.get("source_text"))

    if req_type == "skill":
        terms = requirement_terms(req.get("skill") or req.get("value") or "")
        return bool(terms & facts["expanded_skills"]) or source in facts["text"]
    if req_type == "education":
        wants_bachelors = any(word in value or word in source for word in ("bachelor", "b.s", "bs"))
        return not wants_bachelors or "b.s" in facts["text"] or "bachelor" in facts["text"]
    if req_type == "years":
        min_years = req.get("min_years")
        return min_years is None or facts["years"] >= float(min_years)
    if req_type == "location":
        return "remote" in source or "united states" in source or "usa" in source
    if req_type in REVIEW_TYPES:
        return bool(facts["attested"].get(req_type))
    return norm(requirement_label(req)) in facts["text"]


def missing_reason(facts: dict, req: dict) -> str:
    req_type = req.get("type")
    if req_type in REVIEW_TYPES:
        return "missing_attested_profile_fact"
    if req_type == "location" and not facts["attested"].get("location"):
        return "missing_attested_profile_fact"
    if req_type == "skill":
        return "missing_profile_fact_or_exact_match"
    return "unresolved_requirement"


def has_attested_contradiction(facts: dict, req: dict) -> bool:
    req_type = req.get("type")
    attested = facts["attested"]
    label = norm(requirement_label(req))

    if req_type == "citizenship":
        citizenship = norm(attested.get("citizenship"))
        us_person = attested.get("us_person")
        if "u.s" in label or "us citizen" in label or "united states" in label:
            return bool(citizenship and citizenship not in {"us", "usa", "united states"} and us_person is False)
    if req_type == "clearance":
        return norm(attested.get("security_clearance")) == "none"
    if req_type == "authorization":
        requires_sponsorship = attested.get("requires_sponsorship")
        if requires_sponsorship is True and any(
            phrase in label for phrase in ("does not offer", "unable to sponsor", "will not sponsor")
        ):
            return True
    if req_type == "residency":
        current_location = norm(attested.get("current_location") or attested.get("location"))
        return bool(current_location and current_location not in label)
    return False


def should_block_when_missing(facts: dict, req: dict) -> bool:
    req_type = req.get("type")
    label = norm(
        " ".join(
            str(part or "")
            for part in (req.get("skill"), req.get("value"), req.get("source_text"))
        )
    )

    if req_type == "years":
        return False
    if req_type in CONSEQUENTIAL_TYPES:
        return has_attested_contradiction(facts, req)
    if req_type == "location" and not facts["attested"].get("location"):
        return False
    if req_type == "skill":
        return False
    return True


def evaluate(profile: dict, requirements: dict, attested: dict | None = None, years: float | None = None) -> Decision:
    facts = profile_facts(profile, attested=attested, years=years)
    decision = Decision(
        action="REVIEW",
        years_min=requirements.get("years_required", {}).get("min"),
        candidate_years=facts["years"],
    )

    for req in requirements.get("hard_requirements", []):
        state = req.get("verification_state")
        label = requirement_label(req)
        if state == "AMBIGUOUS":
            decision.unresolved.append(label)
            decision.review_reasons.append("ambiguous_requirement")
        if state != "VERIFIED":
            continue
        if req.get("type") == "years":
            continue
        if not has_fact(facts, req):
            if should_block_when_missing(facts, req):
                decision.blocked_by.append(label)
            else:
                decision.unresolved.append(label)
                decision.review_reasons.append(missing_reason(facts, req))

    if decision.blocked_by:
        decision.action = "SKIP_HARD"
        return decision
    if decision.unresolved:
        decision.action = "REVIEW"
        return decision

    years_min = decision.years_min
    if (
        isinstance(years_min, (int, float))
        and years_min >= YEARS_SKIP_MIN
        and facts["years"] < years_min
    ):
        decision.action = "SKIP"
        decision.blocked_by.append(f"{years_min}+ years required")
        return decision

    for pref in requirements.get("preferred", []):
        label = requirement_label(pref)
        terms = requirement_terms(label)
        if bool(terms & facts["expanded_skills"]) or norm(label) in facts["text"]:
            decision.matched.append(label)
        else:
            decision.missing.append(label)

    if isinstance(years_min, (int, float)) and years_min >= YEARS_STRETCH_MIN:
        decision.action = "STRETCH"
    elif len(decision.matched) >= len(decision.missing):
        decision.action = "APPLY"
    else:
        decision.action = "REVIEW"
    return decision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--requirements", default="requirements_test.json")
    args = parser.parse_args()

    profile = load_profile(args.user_id)
    db = SessionLocal()
    try:
        attested = load_attested_facts(db, args.user_id)
        years = compute_professional_swe_years(db, args.user_id)
    finally:
        db.close()
    items = json.loads(Path(args.requirements).read_text())

    counts = {}
    review_reason_counts = {}
    for item in items:
        if "requirements" not in item:
            continue
        decision = evaluate(profile, item["requirements"], attested=attested, years=years)
        counts[decision.action] = counts.get(decision.action, 0) + 1
        for reason in set(decision.review_reasons):
            review_reason_counts[reason] = review_reason_counts.get(reason, 0) + 1
        print(f"{decision.action:9} {item['company']} - {item['title']}")
        print(f"  years: candidate={decision.candidate_years:g} required={decision.years_min}")
        if decision.blocked_by:
            print(f"  blocked: {'; '.join(decision.blocked_by[:3])}")
        if decision.unresolved:
            print(f"  review: {'; '.join(decision.unresolved[:3])}")
            print(f"  review reasons: {', '.join(sorted(set(decision.review_reasons)))}")
        print(f"  preferred: matched={len(decision.matched)} missing={len(decision.missing)}")

    print("\nsummary")
    for action, count in sorted(counts.items()):
        print(f"{action:9} {count}")
    if review_reason_counts:
        print("\nreview reasons")
        for reason, count in sorted(review_reason_counts.items()):
            print(f"{reason:34} {count}")


if __name__ == "__main__":
    main()
