import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.packet_builder import build_packet  # noqa: E402

DECISION_SCORE_MIN = {
    "APPLY": 70,
    "STRETCH": 55,
    "REVIEW": 40,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", default="APPLY,STRETCH")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--profile-version", type=int, default=1)
    return parser.parse_args()


def candidate_matches(db, decisions: set[str], limit: int):
    min_score = min(DECISION_SCORE_MIN.get(decision, 101) for decision in decisions)
    return (
        db.query(models.JobMatch)
        .filter(models.JobMatch.overall_score >= min_score)
        .order_by(models.JobMatch.overall_score.desc())
        .limit(limit)
        .all()
    )


def main() -> None:
    args = parse_args()
    decisions = {item.strip().upper() for item in args.decision.split(",") if item.strip()}
    db = SessionLocal()
    try:
        built = 0
        for match in candidate_matches(db, decisions, args.limit):
            existing = (
                db.query(models.ApplicationPacket)
                .filter(
                    models.ApplicationPacket.job_id == match.job_id,
                    models.ApplicationPacket.profile_version == args.profile_version,
                )
                .first()
            )
            if existing:
                print(f"skip existing packet {existing.id} for job {match.job_id}")
                continue
            packet = build_packet(db, match.job_id, args.profile_version)
            db.commit()
            built += 1
            print(f"{packet.status} packet {packet.id} for job {packet.job_id}")
        print(f"built {built} packets")
    finally:
        db.close()


if __name__ == "__main__":
    main()
