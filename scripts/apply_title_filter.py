import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

V1 = 1
V2 = 2
V3 = 3

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
V3_SENIORITY_PATTERN = (
    r"\y(staff|principal|distinguished|fellow|architect|director|vp|"
    r"vice president|head of|manager|lead engineer|engineering lead|"
    r"lead software engineer|lead backend engineer|lead frontend engineer|"
    r"lead full.?stack engineer|lead platform engineer|lead data engineer|"
    r"lead machine learning engineer|lead ml engineer|lead ai engineer|"
    r"lead security engineer|lead devops engineer)\y"
)
V1_SWE_TITLE_PATTERN = (
    r"\y(software engineer|software developer|backend|back.?end|frontend|"
    r"front.?end|full.?stack|platform engineer|infrastructure engineer|"
    r"systems engineer|distributed systems|site reliability|sre|devops|"
    r"machine learning engineer|ml engineer|ai engineer|applied scientist|"
    r"research engineer|data engineer|sde|swe|member of technical staff|"
    r"web developer|application developer)\y"
)
V2_SWE_TITLE_PATTERN = (
    r"\y(software engineer|software developer|backend|back.?end|frontend|"
    r"front.?end|full.?stack|platform engineer|infrastructure engineer|"
    r"systems engineer|distributed systems|site reliability|sre|devops|"
    r"machine learning engineer|ml engineer|ai engineer|applied scientist|"
    r"research engineer|data engineer|data scientist|sde|swe|"
    r"member of technical staff|web developer|application developer|"
    r"react engineer|react native engineer|ios engineer|android engineer|"
    r"mobile engineer|qa automation engineer|security engineer|"
    r"release engineer)\y"
)
V3_LOCATION_PATTERN = r"(United States|USA|, [A-Z]{2}\y|Remote)"
V3_CLEARANCE_TITLE_PATTERN = (
    r"\y(ts/sci|top secret|security clearance|polygraph|public trust|"
    r"active clearance)\y"
)
V3_EARLY_CAREER_PATTERN = r"\y(new grad|new graduate|entry|entry level|junior|intern)\y"

FILTERS = {
    "v1": {
        "version": V1,
        "role_head": V1_ROLE_HEAD_PATTERN,
        "wrong_discipline": V1_WRONG_DISCIPLINE_PATTERN,
        "seniority": V1_SENIORITY_PATTERN,
        "swe_title": V1_SWE_TITLE_PATTERN,
    },
    "v2": {
        "version": V2,
        "role_head": V1_ROLE_HEAD_PATTERN,
        "wrong_discipline": V1_WRONG_DISCIPLINE_PATTERN,
        "seniority": V1_SENIORITY_PATTERN,
        "swe_title": V2_SWE_TITLE_PATTERN,
    },
    "v3": {
        "version": V3,
        "role_head": V1_ROLE_HEAD_PATTERN,
        "wrong_discipline": V1_WRONG_DISCIPLINE_PATTERN,
        "seniority": V3_SENIORITY_PATTERN,
        "swe_title": V2_SWE_TITLE_PATTERN,
        "location": V3_LOCATION_PATTERN,
        "clearance_title": V3_CLEARANCE_TITLE_PATTERN,
        "seniority_exemption": V3_EARLY_CAREER_PATTERN,
    },
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
                WHERE eligible IS NULL
                  AND title ~* :pattern
                  AND (:exemption IS NULL OR title !~* :exemption)
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected["seniority"],
                exemption=selected.get("seniority_exemption"),
            ),
            text(
                """
                UPDATE jobs
                SET eligible = false, skip_reason = 'clearance_title', filter_version = :version
                WHERE eligible IS NULL
                  AND :pattern IS NOT NULL
                  AND title ~* :pattern
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected.get("clearance_title"),
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
                SET eligible = false, skip_reason = 'stale_posting', filter_version = :version
                WHERE eligible = true
                  AND :location_pattern IS NOT NULL
                  AND date_posted IS NOT NULL
                  AND date_posted <= now() - interval '30 days'
                """
            ).bindparams(
                version=selected["version"],
                location_pattern=selected.get("location"),
            ),
            text(
                """
                UPDATE jobs
                SET eligible = false, skip_reason = 'non_us_location', filter_version = :version
                WHERE eligible = true
                  AND :pattern IS NOT NULL
                  AND location IS NOT NULL
                  AND location !~* :pattern
                """
            ).bindparams(
                version=selected["version"],
                pattern=selected.get("location"),
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
    parser.add_argument("--version", choices=sorted(FILTERS), default="v3")
    parser.add_argument("--review-limit", type=int, default=40)
    args = parser.parse_args()

    apply_filter(args.version)
    print_review(args.review_limit)


if __name__ == "__main__":
    main()
