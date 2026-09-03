import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402


PROJECT_WEIGHTS = {
    "careeros": 5,
    "yomeets": 4,
    "jobprepai": 3,
    "traceback": 2,
    "twinguard": 1,
}


def fact_rows(project: str, data: dict) -> list[dict]:
    weight = PROJECT_WEIGHTS[project]
    rows = []
    seen = set()
    for fact in data.get("facts", []):
        tier = fact.get("tier", "OBSERVED")
        if tier == "CONFLICTED":
            continue
        claim = str(fact.get("claim", "")).strip()
        if claim:
            add_row(rows, seen, "project_fact", claim, tier, project, weight)
        for tech in fact.get("technologies", []):
            value = str(tech).strip()
            if value:
                add_row(rows, seen, "skill", value, tier, project, weight)
    return rows


def add_row(
    rows: list[dict],
    seen: set[tuple[str, str, str]],
    key: str,
    value: str,
    tier: str,
    project: str,
    weight: int,
) -> None:
    identity = (project, key, value.lower())
    if identity in seen:
        return
    seen.add(identity)
    rows.append(
        {
            "fact_key": key,
            "fact_value": value,
            "tier": tier,
            "source": "repo_extraction",
            "project": project,
            "project_weight": weight,
        }
    )


def load_project(db, user_id: str, project: str, path: Path) -> int:
    data = json.loads(path.read_text())
    rows = fact_rows(project, data)
    db.query(models.CandidateFact).filter(
        models.CandidateFact.user_id == user_id,
        models.CandidateFact.project == project,
        models.CandidateFact.tier != "ATTESTED",
    ).delete(synchronize_session=False)
    for row in rows:
        db.add(models.CandidateFact(user_id=user_id, **row))
    return len(rows)


def parse_project_arg(value: str) -> tuple[str, Path]:
    project, path = value.split("=", 1)
    project = project.strip().lower()
    if project not in PROJECT_WEIGHTS:
        raise ValueError(f"unknown project: {project}")
    return project, Path(path).expanduser()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--project", action="append", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        total = 0
        for raw in args.project:
            project, path = parse_project_arg(raw)
            count = load_project(db, args.user_id, project, path)
            total += count
            print(f"{project}: {count} facts")
        db.commit()
        print(f"total: {total} facts")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
