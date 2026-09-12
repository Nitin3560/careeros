import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.packet_builder import build_packet  # noqa: E402
import test_evidence_matcher as matcher  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", default="APPLY,STRETCH")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--profile-version", type=int, default=1)
    return parser.parse_args()


def candidate_matches(db, decisions: set[str], limit: int):
    profile = matcher.load_profile(matcher.DEFAULT_USER_ID)
    attested = matcher.load_attested_facts(db, matcher.DEFAULT_USER_ID)
    years = matcher.compute_professional_swe_years(db, matcher.DEFAULT_USER_ID)
    rows = []
    for item in matcher.load_db_items(None):
        decision = matcher.evaluate(
            profile,
            item["requirements"],
            attested=attested,
            years=years,
            job_context=item,
        )
        if decision.action in decisions:
            rows.append((item, decision))

    rows.sort(key=matcher.fit_sort_key, reverse=True)
    return rows[:limit]


def main() -> None:
    args = parse_args()
    decisions = {item.strip().upper() for item in args.decision.split(",") if item.strip()}
    db = SessionLocal()
    try:
        built = 0
        for item, decision in candidate_matches(db, decisions, args.limit):
            job_id = item["job_id"]
            existing = (
                db.query(models.ApplicationPacket)
                .filter(
                    models.ApplicationPacket.job_id == job_id,
                    models.ApplicationPacket.profile_version == args.profile_version,
                )
                .first()
            )
            if existing:
                print(f"skip existing packet {existing.id} for job {job_id}")
                continue
            print(
                f"building {decision.action} packet for {item['company']} - {item['title']} "
                f"(matched={len(decision.matched)} missing={len(decision.missing)})"
            )
            packet = build_packet(db, job_id, args.profile_version)
            db.commit()
            built += 1
            print(f"{packet.status} packet {packet.id} for job {packet.job_id}")
        print(f"built {built} packets")
    finally:
        db.close()


if __name__ == "__main__":
    main()
