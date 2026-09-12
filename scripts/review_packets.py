import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def _print_packet(db, packet: models.ApplicationPacket) -> None:
    job = db.query(models.Job).filter(models.Job.id == packet.job_id).first()
    match = db.query(models.JobMatch).filter(models.JobMatch.job_id == packet.job_id).first()
    requirements = db.query(models.JobRequirement).filter(models.JobRequirement.job_id == packet.job_id).first()

    print("=" * 80)
    print(f"packet: {packet.id} [{packet.status}]")
    if packet.blocked_reason:
        print(f"blocked/rejected reason: {packet.blocked_reason}")
    if job:
        print(f"job: {job.title} at {job.company}")
    if match:
        print(f"decision score: {match.overall_score}")
        print(f"matched: {', '.join(match.strengths or [])}")
        print(f"missing: {', '.join(match.missing or [])}")
    if requirements:
        print(f"requirements status: {requirements.status}")

    print("\nbullets:")
    for bullet in packet.bullets or []:
        print(f"- {bullet.get('text')}")
        print(f"  fact ids: {', '.join(bullet.get('source_fact_ids') or [])}")
        print(f"  provenance tiers: {', '.join(bullet.get('provenance_tiers') or [])}")

    if packet.rejected_claims:
        print("\nrejected claims:")
        for rejected in packet.rejected_claims:
            print(f"- {rejected.get('text')}")
            for violation in rejected.get("violations", []):
                print(f"  violation: {violation.get('kind')} -> {violation.get('span')}")

    print("\ncover letter:")
    print(packet.cover_letter or "")
    print("\nanswers:")
    for question, answer in (packet.answers or {}).items():
        print(f"Q: {question}\nA: {answer}")
    print(f"\nresume path: {packet.resume_path or ''}")


def main() -> None:
    db = SessionLocal()
    try:
        packets = (
            db.query(models.ApplicationPacket)
            .order_by(models.ApplicationPacket.created_at.desc())
            .limit(25)
            .all()
        )
        for packet in packets:
            _print_packet(db, packet)
            action = input("[approve] [reject] [edit] > ").strip().lower()
            if action == "approve":
                packet.status = "ready"
                packet.blocked_reason = None
            elif action == "reject":
                packet.status = "rejected"
                packet.blocked_reason = "rejected during manual review"
            elif action == "edit":
                print(f"edit packet {packet.id} directly, then rerun review")
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
