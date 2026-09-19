import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402

START_MARKER = "<!-- ENTRY_JOBS:START -->"
END_MARKER = "<!-- ENTRY_JOBS:END -->"

ENTRY_TITLE_RE = re.compile(
    r"\b(new grad|new graduate|university grad|university graduate|college grad|"
    r"recent grad|graduate software|early career|entry[- ]level|junior|"
    r"software engineer\s*(i|1)\b|software development engineer\s*(i|1)\b|"
    r"sde\s*(i|1)\b|engineer\s*(i|1)\b|member of technical staff|"
    r"mts\b|associate software engineer|graduate engineer)\b",
    re.I,
)
EXCLUDE_TITLE_RE = re.compile(
    r"\b(intern|internship|co-?op|apprentice|senior|sr\.?|staff|principal|lead|"
    r"manager|architect|director|head of|vp)\b",
    re.I,
)
FULL_TIME_HINT_RE = re.compile(r"\b(full[- ]time|regular|permanent)\b", re.I)
DEFENSE_RE = re.compile(
    r"\b(itar|u\.s\. person|us person|security clearance|clearance|top secret|ts/sci|classified)\b",
    re.I,
)


@dataclass(frozen=True)
class EntryJob:
    company: str
    title: str
    location: str | None
    date_posted: datetime | None
    first_seen_at: datetime
    application_url: str | None
    source: str


def as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_entry_full_time_title(title: str, description: str | None = None) -> bool:
    text_blob = f"{title}\n{description or ''}"
    if DEFENSE_RE.search(text_blob):
        return False
    # MTS-style postings can be full-time entry roles, and the phrase contains
    # "Staff", so handle it before the senior/staff exclusion.
    if re.search(r"\b(member of technical staff|mts)\b", title, re.I):
        return True
    if EXCLUDE_TITLE_RE.search(title):
        return False
    if ENTRY_TITLE_RE.search(title):
        return True
    return False


def fetch_jobs(since_hours: int, limit: int) -> list[EntryJob]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (coalesce(canonical_url, application_url, external_id))
                       company, title, location, date_posted, first_seen_at,
                       application_url, source, description_text
                FROM jobs
                WHERE first_seen_at > now() - (:hours * interval '1 hour')
                  AND application_url IS NOT NULL
                ORDER BY coalesce(canonical_url, application_url, external_id),
                         first_seen_at DESC, date_posted DESC NULLS LAST
                """
            ),
            {"hours": since_hours},
        ).all()
    finally:
        db.close()

    jobs: list[EntryJob] = []
    for company, title, location, date_posted, first_seen_at, application_url, source, description in rows:
        if is_entry_full_time_title(title, description):
            jobs.append(
                EntryJob(
                    company=company,
                    title=title,
                    location=location,
                    date_posted=as_aware(date_posted),
                    first_seen_at=as_aware(first_seen_at) or datetime.now(timezone.utc),
                    application_url=application_url,
                    source=source,
                )
            )

    jobs.sort(
        key=lambda job: (
            job.date_posted or job.first_seen_at,
            job.first_seen_at,
        ),
        reverse=True,
    )
    return jobs[:limit]


def escape_cell(value: object) -> str:
    text_value = str(value or "").replace("\n", " ").strip()
    return text_value.replace("|", "\\|")


def render_markdown(jobs: list[EntryJob], since_hours: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        START_MARKER,
        "## New Grad & Entry-Level Engineering Roles",
        "",
        f"Auto-updated from CareerOS at **{now}**. Showing full-time entry-level signals from the last **{since_hours} hours**.",
        "",
    ]
    if not jobs:
        lines.extend(["No matching roles found in the current window.", "", END_MARKER])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Company | Role | Location | Posted | Source | Apply |",
            "|---|---|---|---|---|---|",
        ]
    )
    for job in jobs:
        posted = (job.date_posted or job.first_seen_at).strftime("%Y-%m-%d")
        apply = f"[Apply]({job.application_url})" if job.application_url else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(job.company),
                    escape_cell(job.title),
                    escape_cell(job.location),
                    escape_cell(posted),
                    escape_cell(job.source),
                    apply,
                ]
            )
            + " |"
        )
    lines.extend(["", END_MARKER])
    return "\n".join(lines) + "\n"


def update_readme(path: Path, block: str) -> bool:
    if path.exists():
        content = path.read_text()
    else:
        content = "# New Grad Software Jobs\n\n"

    if START_MARKER in content and END_MARKER in content:
        pattern = re.compile(
            re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER) + r"\n?",
            re.S,
        )
        updated = pattern.sub(block, content)
    else:
        suffix = "" if content.endswith("\n") else "\n"
        updated = content + suffix + "\n" + block

    if updated == content:
        return False
    path.write_text(updated)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    parser.add_argument("--since-hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    jobs = fetch_jobs(args.since_hours, args.limit)
    block = render_markdown(jobs, args.since_hours)
    changed = update_readme(Path(args.readme), block)
    print(f"entry_jobs={len(jobs)} readme={args.readme} changed={changed}")


if __name__ == "__main__":
    main()
