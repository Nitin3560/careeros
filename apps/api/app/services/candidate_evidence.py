from datetime import date

from sqlalchemy.orm import Session

from app import models

SKILL_FACT_KEYS = {
    "skill",
    "skills",
    "technology",
    "technologies",
    "tool",
    "tools",
    "framework",
    "frameworks",
}
ROLE_FACT_KEYS = {"preferred_role", "preferred_roles", "target_role", "target_roles"}
EDUCATION_FACT_KEYS = {"degree", "education"}
ATTESTED_TIER = "ATTESTED"


def load_attested_facts(db: Session, user_id: str) -> dict:
    rows = (
        db.query(models.CandidateFact)
        .filter(
            models.CandidateFact.user_id == user_id,
            models.CandidateFact.tier == "ATTESTED",
        )
        .all()
    )
    return {row.fact_key: parse_fact_value(row.fact_value) for row in rows}


def load_candidate_fact_profile(db: Session, user_id: str) -> dict:
    rows = (
        db.query(models.CandidateFact)
        .filter(models.CandidateFact.user_id == user_id)
        .all()
    )

    skills = []
    preferred_roles = []
    education = []
    highlights = []

    for row in rows:
        if row.tier == ATTESTED_TIER:
            continue
        key = row.fact_key.strip().lower()
        value = row.fact_value.strip()
        if not value:
            continue
        weight = max(1, getattr(row, "project_weight", 1) or 1)
        if key in SKILL_FACT_KEYS or key.startswith("skill:"):
            skills.append({"name": value, "evidence": [value], "weight": weight})
        elif key in ROLE_FACT_KEYS or key.startswith("role:"):
            preferred_roles.append(value)
        elif key in EDUCATION_FACT_KEYS or key.startswith("education:"):
            education.append({"degree": value, "institution": "", "year": ""})
        else:
            highlights.append(value)

    return {
        "skills": skills,
        "education": education,
        "experience": [
            {
                "title": "Evidence facts",
                "company": "Candidate evidence",
                "duration": "",
                "highlights": highlights,
            }
        ]
        if highlights
        else [],
        "preferred_roles": preferred_roles,
    }


def has_candidate_evidence(profile: dict) -> bool:
    return any(
        profile.get(key)
        for key in ("skills", "education", "experience", "preferred_roles")
    )


def parse_fact_value(value: str):
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return value


def compute_professional_swe_years(db: Session, user_id: str, as_of: date | None = None) -> float:
    as_of = as_of or date.today()
    rows = (
        db.query(models.CandidateEmployment)
        .filter(models.CandidateEmployment.user_id == user_id)
        .all()
    )
    total_days = 0
    for row in rows:
        if row.employment_type not in {"full_time", "internship", "contract"}:
            continue
        end_date = row.end_date or as_of
        if end_date <= row.start_date:
            continue
        total_days += (end_date - row.start_date).days
    return round(total_days / 365.25, 2)
