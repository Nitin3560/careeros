import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

V1 = 1

V1_ROLE_HEAD_PATTERN = (
    r"\y(sales|solutions?|support|field|service|customer|forward.?deployed|"
    r"implementation|pre.?sales|partner|deployment|integration|"
    r"technical account)\s+engineer\y"
)
V1_WRONG_DISCIPLINE_PATTERN = (
    r"\y(mechanical|electrical|civil|chemical|industrial|hardware|firmware|"
    r"process|manufacturing|packaging|optical|rf|asic|analog|structural)\y"
)
V1_SENIORITY_PATTERN = (
    r"\y(staff|principal|distinguished|fellow|architect|director|vp|"
    r"vice president|head of|manager|lead engineer|engineering lead)\y"
)
V1_SWE_TITLE_PATTERN = (
    r"\y(software engineer|software developer|backend|back.?end|frontend|"
    r"front.?end|full.?stack|platform engineer|infrastructure engineer|"
    r"systems engineer|distributed systems|site reliability|sre|devops|"
    r"machine learning engineer|ml engineer|ai engineer|applied scientist|"
    r"research engineer|data engineer|sde|swe|member of technical staff|"
    r"web developer|application developer)\y"
)

FILTERS = {
    "v1": {
        "version": V1,
        "role_head": V1_ROLE_HEAD_PATTERN,
        "wrong_discipline": V1_WRONG_DISCIPLINE_PATTERN,
        "seniority": V1_SENIORITY_PATTERN,
        "swe_title": V1_SWE_TITLE_PATTERN,
    }
}

ROLE_HEAD_PATTERN = V1_ROLE_HEAD_PATTERN
WRONG_DISCIPLINE_PATTERN = V1_WRONG_DISCIPLINE_PATTERN
SENIORITY_PATTERN = V1_SENIORITY_PATTERN
SWE_TITLE_PATTERN = V1_SWE_TITLE_PATTERN


def apply_filter(filter_name: str = "v1"):
    selected = FILTERS[filter_name]
    db = SessionLocal()
    try:
        statements = [
            text(
                "UPDATE jobs SET eligible = NULL, skip_reason = NULL, "
                "matched_pattern = NULL, filter_version = NULL"
            ),
            text(
                """
                UPDATE jobs
                SET eligible = false, skip_reason = 'role_head', filter_version = :version
                WHERE title ~* :pattern
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected["role_head"],
            ),
            text(
                """
                UPDATE jobs
                SET eligible = false, skip_reason = 'wrong_discipline', filter_version = :version
                WHERE eligible IS NULL AND title ~* :pattern
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected["wrong_discipline"],
            ),
            text(
                """
                UPDATE jobs
                SET eligible = false, skip_reason = 'seniority', filter_version = :version
                WHERE eligible IS NULL AND title ~* :pattern
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected["seniority"],
            ),
            text(
                """
                UPDATE jobs
                SET eligible = true, skip_reason = NULL, matched_pattern = 'swe_title',
                    filter_version = :version
                WHERE eligible IS NULL AND title ~* :pattern
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected["swe_title"],
            ),
            text(
                """
                UPDATE jobs
                SET eligible = false, skip_reason = 'no_title_match', filter_version = :version
                WHERE eligible IS NULL
                """
            ).bindparams(version=selected["version"]),
        ]
        for statement in statements:
            db.execute(statement)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def print_review(limit: int):
    db = SessionLocal()
    try:
        print("skip_reason_counts")
        rows = db.execute(
            text(
                """
                SELECT coalesce(skip_reason, 'eligible') AS reason, count(*)
                FROM jobs GROUP BY 1 ORDER BY 2 DESC
                """
            )
        ).all()
        for reason, count in rows:
            print(f"{reason:20} {count}")

        print("\nreview_excluded")
        rows = db.execute(
            text(
                """
                SELECT title, skip_reason, count(*)
                FROM jobs
                WHERE eligible = false AND skip_reason IN ('role_head','seniority')
                GROUP BY 1,2 ORDER BY 3 DESC LIMIT :limit
                """
            ),
            {"limit": limit},
        ).all()
        for title, reason, count in rows:
            print(f"{count:>4}  {reason:12} {title}")

        print("\nreview_eligible")
        rows = db.execute(
            text(
                """
                SELECT title, count(*)
                FROM jobs
                WHERE eligible = true
                GROUP BY 1 ORDER BY 2 DESC LIMIT :limit
                """
            ),
            {"limit": limit},
        ).all()
        for title, count in rows:
            print(f"{count:>4}  {title}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=sorted(FILTERS), default="v1")
    parser.add_argument("--review-limit", type=int, default=40)
    args = parser.parse_args()

    apply_filter(args.version)
    print_review(args.review_limit)


if __name__ == "__main__":
    main()
