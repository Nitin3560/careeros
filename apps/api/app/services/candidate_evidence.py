from datetime import date

from sqlalchemy.orm import Session

from app import models


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
