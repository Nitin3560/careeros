import argparse
import re
import sys
from dataclasses import dataclass
from collections import defaultdict
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
    r"manager|architect|director|head of|vp|sales|account executive|analyst|"
    r"product design|designer|support|customer|recruiter)\b",
    re.I,
)
TECH_TITLE_RE = re.compile(
    r"\b(software|sde|developer|backend|frontend|front[- ]?end|full[- ]?stack|"
    r"platform|infrastructure|site reliability|sre|devops|machine learning|ml|ai|"
    r"data engineer|member of technical staff|mts|firmware|embedded|systems engineer|"
    r"security engineer|cloud engineer|mobile engineer|ios engineer|android engineer)\b",
    re.I,
)
US_LOCATION_RE = re.compile(
    r"\b(United States|USA|US Remote|Remote US|Remote - US|Remote, US|Remote in the US|"
    r"US-Remote|Remote - United States)\b|"
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|"
    r"TX|UT|VT|VA|WA|WV|WI|WY|DC)\b|"
    r"\b(California|Washington|New York|Texas|Massachusetts|Virginia|Colorado|Illinois|"
    r"New Jersey|Michigan|Florida|Georgia|North Carolina|Oregon|Arizona|Ohio|Pennsylvania|"
    r"Tennessee|Utah|Wisconsin|Minnesota|Missouri|Connecticut|Maryland|Indiana)\b",
    re.I,
)
NON_US_LOCATION_RE = re.compile(
    r"\b(United Kingdom|England|London|Canada|Toronto|Vancouver|Poland|Romania|"
    r"Vietnam|Singapore|India|Bengaluru|Prague|Czech|Qatar|Doha|Ireland|Dublin|"
    r"Netherlands|Germany|France|Spain|Mexico|Brazil|Australia|Taiwan|Japan)\b",
    re.I,
)
FULL_TIME_HINT_RE = re.compile(r"\b(full[- ]time|regular|permanent)\b", re.I)
DEFENSE_RE = re.compile(
    r"\b(itar|u\.s\. person|us person|security clearance|clearance|top secret|ts/sci|classified)\b",
    re.I,
)
TIER_A_COMPANY_RE = re.compile(
    r"\b(stripe|amazon|google|microsoft|meta|apple|nvidia|openai|anthropic|databricks|"
    r"snowflake|cloudflare|figma|notion|linear|cursor|perplexity|reddit|roblox|block|"
    r"coinbase|brex|pinterest|waymo|airbnb|uber|lyft|doordash|instacart|mongodb|"
    r"gitlab|github|atlassian)\b",
    re.I,
)
TIER_B_COMPANY_RE = re.compile(
    r"\b(samsara|elastic|clear|idme|lightningai|rdccareers|zoominfo|abnormalsecurity|"
    r"upstart|affirm|chime|mercury|fivetran|klaviyo|scaleai|grafanalabs|mozilla|"
    r"backblaze|sezzle|oura|nexhealth)\b",
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
    salary: str | None = None


def as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_us_location(location: str | None) -> bool:
    if not location:
        return False
    if NON_US_LOCATION_RE.search(location):
        return False
    return US_LOCATION_RE.search(location) is not None


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
    if not TECH_TITLE_RE.search(title):
        return False
    if ENTRY_TITLE_RE.search(title):
        return True
    return False


def extract_salary(text: str | None) -> str:
    if not text:
        return ""
    match = re.search(
        r"(\$\s?\d{2,3}(?:,\d{3})?(?:\s?[kK])?\s?(?:-|–|to)\s?\$?\s?\d{2,3}(?:,\d{3})?(?:\s?[kK])?)",
        text,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).replace("$ ", "$")
    match = re.search(r"(\$\s?\d{2,3}(?:,\d{3})?(?:\s?[kK])?\s?(?:/|per)\s?(?:year|yr|hour|hr))", text, re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).replace("$ ", "$")
    return ""


def tier_for_job(job: EntryJob) -> str:
    company_title = f"{job.company} {job.title}"
    if TIER_A_COMPANY_RE.search(job.company):
        return "Tier A"
    if TIER_B_COMPANY_RE.search(job.company):
        return "Tier B"
    if re.search(r"\b(new grad|new graduate|university grad|university graduate|early career|software engineer\s*(i|1)|software development engineer\s*(i|1)|sde\s*(i|1))\b", company_title, re.I):
        return "Tier B"
    return "Tier C"


def fetch_jobs(since_hours: int, limit: int) -> list[EntryJob]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (coalesce(j.canonical_url, j.application_url, j.external_id))
                       j.company, j.title, j.location, j.date_posted, j.first_seen_at,
                       j.application_url, j.source, j.description_text
                FROM jobs j
                WHERE j.first_seen_at > now() - (:hours * interval '1 hour')
                  AND j.application_url IS NOT NULL
                ORDER BY coalesce(j.canonical_url, j.application_url, j.external_id),
                         j.first_seen_at DESC, j.date_posted DESC NULLS LAST
                """
            ),
            {"hours": since_hours},
        ).all()
    finally:
        db.close()

    jobs: list[EntryJob] = []
    for company, title, location, date_posted, first_seen_at, application_url, source, description in rows:
        if is_us_location(location) and is_entry_full_time_title(title, description):
            jobs.append(
                EntryJob(
                    company=company,
                    title=title,
                    location=location,
                    date_posted=as_aware(date_posted),
                    first_seen_at=as_aware(first_seen_at) or datetime.now(timezone.utc),
                    application_url=application_url,
                    source=source,
                    salary=extract_salary(description),
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


def render_tier_table(jobs: list[EntryJob]) -> list[str]:
    if not jobs:
        return ["No matching roles in this tier right now.", ""]

    lines = [
        "| Company | Role | Posted | Found | Salary | Apply |",
        "|---|---|---|---|---|---|",
    ]
    for job in jobs:
        apply = f"[Apply]({job.application_url})" if job.application_url else ""
        role = job.title
        if job.location:
            role = f"{role}<br><sub>{escape_cell(job.location)}</sub>"
        posted = (job.date_posted or job.first_seen_at).strftime("%Y-%m-%d")
        found = job.first_seen_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(job.company),
                    role.replace("|", "\\|"),
                    escape_cell(posted),
                    escape_cell(found),
                    escape_cell(job.salary),
                    apply,
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def render_markdown(jobs: list[EntryJob], since_hours: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tiers: dict[str, list[EntryJob]] = defaultdict(list)
    for job in jobs:
        tiers[tier_for_job(job)].append(job)

    lines = [
        START_MARKER,
        "## New Grad & Entry-Level Engineering Roles",
        "",
        f"Auto-updated hourly from CareerOS. Last run: **{now}**. Showing only postings found in the last **7 days**.",
        "",
        "Quick links: [Tier A](#tier-a) · [Tier B](#tier-b) · [Tier C](#tier-c)",
        "",
        "### Tier A",
        "",
        *render_tier_table(tiers["Tier A"]),
        "### Tier B",
        "",
        *render_tier_table(tiers["Tier B"]),
        "### Tier C",
        "",
        *render_tier_table(tiers["Tier C"]),
        END_MARKER,
    ]
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
    parser.add_argument("--since-hours", type=int, default=168)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    jobs = fetch_jobs(args.since_hours, args.limit)
    block = render_markdown(jobs, args.since_hours)
    changed = update_readme(Path(args.readme), block)
    print(f"entry_jobs={len(jobs)} readme={args.readme} changed={changed}")


if __name__ == "__main__":
    main()
