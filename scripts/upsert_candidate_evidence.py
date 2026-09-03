import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def parse_employment(value: str) -> dict:
    parts = value.split("|")
    if len(parts) != 6:
        raise ValueError(
            "employment must be company|title|start_date|end_date|type|is_current"
        )
    company, title, start_date, end_date, employment_type, is_current = parts
    return {
        "company": company,
        "title": title,
        "start_date": date.fromisoformat(start_date),
        "end_date": (
            None
            if end_date.lower() in {"", "none", "present"}
            else date.fromisoformat(end_date)
        ),
        "employment_type": employment_type,
        "is_current": is_current.strip().lower() == "true",
    }


def upsert_fact(db, user_id: str, key: str, value: str):
    fact = (
        db.query(models.CandidateFact)
        .filter(
            models.CandidateFact.user_id == user_id,
            models.CandidateFact.fact_key == key,
        )
        .first()
    )
    if fact:
        fact.fact_value = value
        fact.tier = "ATTESTED"
        fact.source = "user"
        return
    db.add(
        models.CandidateFact(
            user_id=user_id,
            fact_key=key,
            fact_value=value,
            tier="ATTESTED",
            source="user",
        )
    )


def replace_employment(db, user_id: str, entries: list[dict]):
    db.query(models.CandidateEmployment).filter(
        models.CandidateEmployment.user_id == user_id
    ).delete()
    for entry in entries:
        db.add(models.CandidateEmployment(user_id=user_id, **entry))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--fact", action="append", default=[])
    parser.add_argument("--employment", action="append", default=[])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        for fact in args.fact:
            key, value = fact.split("=", 1)
            upsert_fact(db, args.user_id, key.strip(), value.strip())
        if args.employment:
            replace_employment(
                db,
                args.user_id,
                [parse_employment(value) for value in args.employment],
            )
        db.commit()
        print(f"facts upserted: {len(args.fact)}")
        print(f"employment rows replaced: {len(args.employment)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
