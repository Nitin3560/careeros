import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.answer_bank import store_answer  # noqa: E402

ARCHETYPES = [
    "best_project",
    "biggest_challenge",
    "disagreement",
    "recent_learning",
    "strength",
    "weakness",
    "why_swe",
    "proudest_code",
    "failure",
    "teamwork",
    "conflict_resolution",
    "career_goals",
    "why_leaving",
    "side_projects",
    "biggest_impact",
]


def main() -> None:
    db = SessionLocal()
    try:
        for archetype in ARCHETYPES:
            question = archetype.replace("_", " ")
            existing = (
                db.query(models.AnswerBank)
                .filter_by(archetype=archetype, tier="invariant")
                .first()
            )
            if existing:
                continue
            store_answer(
                db,
                question=f"Placeholder: {question}",
                answer=f"TODO: fill in canonical answer for {question}.",
                tier="invariant",
                archetype=archetype,
            )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
