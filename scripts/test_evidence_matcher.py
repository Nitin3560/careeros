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
    has_candidate_evidence,
    load_candidate_fact_profile,
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

ACTION_PRIORITY = {
    "APPLY": 4,
    "STRETCH": 3,
    "REVIEW": 2,
    "SKIP": 1,
    "SKIP_HARD": 0,
}


@dataclass
class Decision:
    action: str
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    matched_weight: int = 0
    missing_weight: int = 0
    blocked_by: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    avoid_domain_hits: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    years_min: int | None = None
    candidate_years: float = 0.0


def norm(value) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", str(value or "").lower()).strip()


def load_profile(user_id: str, allow_legacy_profile: bool = False) -> dict:
    db = SessionLocal()
    try:
        evidence_profile = load_candidate_fact_profile(db, user_id)
        if has_candidate_evidence(evidence_profile):
            return evidence_profile

        if not allow_legacy_profile:
            raise SystemExit(
                "candidate_facts is empty for this user; refusing to match against stale candidate_profiles. "
                "Use --allow-legacy-profile only for debugging."
            )

        row = db.execute(
            text(
                """
                SELECT data, status
                FROM candidate_profiles
                WHERE user_id::text = :user_id
                """
            ),
            {"user_id": user_id},
        ).first()
        if not row:
            raise SystemExit("no legacy candidate profile found")
        if row.status == "SUPERSEDED":
            raise SystemExit("legacy candidate profile is SUPERSEDED")
        return row.data
    finally:
        db.close()


def load_json_items(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def load_db_items(limit: int | None = None) -> list[dict]:
    limit_sql = "LIMIT :limit" if limit else ""
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                f"""
                SELECT j.id, j.title, j.company, j.location, jr.requirements
                FROM job_requirements jr
                JOIN jobs j ON j.id = jr.job_id
                WHERE jr.status = 'ok'
                ORDER BY j.date_posted DESC NULLS LAST
                {limit_sql}
                """
            ),
            {"limit": limit},
        ).fetchall()
    finally:
        db.close()

    return [
        {
            "job_id": str(row.id),
            "title": row.title,
            "company": row.company,
            "location": row.location,
            "requirements": row.requirements,
        }
        for row in rows
    ]


def profile_facts(profile: dict, attested: dict | None = None, years: float | None = None) -> dict:
    skills = {
        norm(skill.get("name"))
        for skill in profile.get("skills", [])
        if isinstance(skill, dict) and skill.get("name")
    }
    expanded_skills = expanded_profile_terms(skills)
    skill_weights = {}
    text_parts = []
    for skill in profile.get("skills", []):
        if isinstance(skill, dict):
            name = norm(skill.get("name", ""))
            weight = max(1, int(skill.get("weight") or 1))
            text_parts.append(skill.get("name", ""))
            text_parts.extend(skill.get("evidence", []))
            for term in expanded_profile_terms({name}):
                skill_weights[term] = max(skill_weights.get(term, 0), weight)
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
        "skill_weights": skill_weights,
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


def split_attested_terms(value) -> list[str]:
    if not value:
        return []
    return [term.strip() for term in str(value).split(",") if term.strip()]


def requirement_text(requirements: dict) -> str:
    labels = []
    for req in requirements.get("hard_requirements", []):
        labels.append(requirement_label(req))
    for req in requirements.get("preferred", []):
        labels.append(requirement_label(req))
    return " ".join(labels)


def avoid_domain_hits(facts: dict, requirements: dict, job_context: dict | None = None) -> list[str]:
    domains = split_attested_terms(facts["attested"].get("avoid_domains"))
    if not domains:
        return []
    context_parts = [
        requirement_text(requirements),
        (job_context or {}).get("title", ""),
        (job_context or {}).get("company", ""),
    ]
    haystack = norm(" ".join(context_parts))
    return [domain for domain in domains if norm(domain) in haystack]


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


def skill_match_weight(facts: dict, label: str) -> int:
    terms = requirement_terms(label)
    weights = [facts["skill_weights"].get(term, 0) for term in terms]
    if weights:
        return max(weights)
    if norm(label) in facts["text"]:
        return 1
    return 0


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

    if req_type == "years":
        return False
    if req_type in CONSEQUENTIAL_TYPES:
        return has_attested_contradiction(facts, req)
    if req_type == "location" and not facts["attested"].get("location"):
        return False
    if req_type == "skill":
        return False
    return True


def evaluate(
    profile: dict,
    requirements: dict,
    attested: dict | None = None,
    years: float | None = None,
    job_context: dict | None = None,
) -> Decision:
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
        if has_fact(facts, req):
            if req.get("type") == "skill":
                decision.matched.append(label)
                decision.matched_weight += skill_match_weight(facts, label) or 1
            continue
        else:
            if req.get("type") == "skill":
                decision.missing.append(label)
                decision.missing_weight += 1
            if should_block_when_missing(facts, req):
                decision.blocked_by.append(label)
            else:
                decision.unresolved.append(label)
                decision.review_reasons.append(missing_reason(facts, req))

    for pref in requirements.get("preferred", []):
        label = requirement_label(pref)
        terms = requirement_terms(label)
        if bool(terms & facts["expanded_skills"]) or norm(label) in facts["text"]:
            decision.matched.append(label)
            decision.matched_weight += skill_match_weight(facts, label) or 1
        else:
            decision.missing.append(label)
            decision.missing_weight += 1

    decision.avoid_domain_hits = avoid_domain_hits(facts, requirements, job_context)
    if decision.avoid_domain_hits:
        decision.unresolved.extend(decision.avoid_domain_hits)
        decision.review_reasons.append("avoid_domain_match")

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

    if decision.matched_weight == 0:
        decision.action = "REVIEW"
        decision.review_reasons.append("no_positive_match_signal")
    elif isinstance(years_min, (int, float)) and years_min >= YEARS_STRETCH_MIN:
        decision.action = "STRETCH"
    elif len(decision.matched) >= len(decision.missing):
        decision.action = "APPLY"
    else:
        decision.action = "REVIEW"
    return decision


def fit_sort_key(row: tuple[dict, Decision]) -> tuple[int, int, int, int]:
    _, decision = row
    return (
        decision.matched_weight,
        -decision.missing_weight,
        ACTION_PRIORITY.get(decision.action, 0),
        -len(decision.avoid_domain_hits),
        -len(decision.unresolved),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--requirements", default="requirements_test.json")
    parser.add_argument("--from-db", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top", type=int)
    parser.add_argument("--allow-legacy-profile", action="store_true")
    args = parser.parse_args()

    profile = load_profile(args.user_id, allow_legacy_profile=args.allow_legacy_profile)
    db = SessionLocal()
    try:
        attested = load_attested_facts(db, args.user_id)
        years = compute_professional_swe_years(db, args.user_id)
    finally:
        db.close()
    items = load_db_items(args.limit) if args.from_db else load_json_items(args.requirements)

    rows = []
    counts = {}
    review_reason_counts = {}
    for item in items:
        if "requirements" not in item:
            continue
        decision = evaluate(
            profile,
            item["requirements"],
            attested=attested,
            years=years,
            job_context=item,
        )
        counts[decision.action] = counts.get(decision.action, 0) + 1
        for reason in set(decision.review_reasons):
            review_reason_counts[reason] = review_reason_counts.get(reason, 0) + 1
        rows.append((item, decision))

    ranked = sorted(rows, key=fit_sort_key, reverse=True)
    if args.top:
        ranked = ranked[: args.top]

    for rank, (item, decision) in enumerate(ranked, start=1):
        matched_preview = "; ".join(decision.matched[:3]) or "-"
        missing_preview = "; ".join(decision.missing[:3]) or "-"
        fit = (
            f"matched={len(decision.matched)} missing={len(decision.missing)} "
            f"weighted={decision.matched_weight}/{decision.missing_weight}"
        )
        print(f"#{rank} {decision.action:9} {fit} {item['company']} - {item['title']}")
        print(f"  years: candidate={decision.candidate_years:g} required={decision.years_min}")
        if decision.blocked_by:
            print(f"  blocked: {'; '.join(decision.blocked_by[:3])}")
        if decision.unresolved:
            print(f"  review: {'; '.join(decision.unresolved[:3])}")
            print(f"  review reasons: {', '.join(sorted(set(decision.review_reasons)))}")
        print(f"  matched: {matched_preview}")
        print(f"  missing: {missing_preview}")

    print("\nsummary")
    for action, count in sorted(counts.items()):
        print(f"{action:9} {count}")
    if review_reason_counts:
        print("\nreview reasons")
        for reason, count in sorted(review_reason_counts.items()):
            print(f"{reason:34} {count}")


if __name__ == "__main__":
    main()
