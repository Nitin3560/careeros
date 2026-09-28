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
    r"\b(intern|internship|co-?op|apprentice|sales|account executive|analyst|"
    r"supervisor|technician|facilities|administrator|product design|designer|support|"
    r"customer|recruiter)\b",
    re.I,
)
TECH_TITLE_RE = re.compile(
    r"\b(software|sde|developer|backend|frontend|front[- ]?end|full[- ]?stack|"
    r"platform|infrastructure|site reliability|sre|devops|machine learning|ml|ai|"
    r"data engineer|data scientist|data science|member of technical staff|mts|firmware|embedded|"
    r"systems engineer|security engineer|cloud engineer|mobile engineer|ios engineer|android engineer)\b",
    re.I,
)
US_LOCATION_RE = re.compile(
    r"\b(United States|USA|US Remote|Remote US|Remote - US|Remote, US|Remote in the US|"
    r"US-Remote|Remote - United States)\b|"
    r"\b(California|Washington|New York|Texas|Massachusetts|Virginia|Colorado|Illinois|"
    r"New Jersey|Michigan|Florida|Georgia|North Carolina|Oregon|Arizona|Ohio|Pennsylvania|"
    r"Tennessee|Utah|Wisconsin|Minnesota|Missouri|Connecticut|Maryland|Indiana)\b",
    re.I,
)
US_STATE_SUFFIX_RE = re.compile(
    r"(?:,|\s)(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|"
    r"VA|WA|WV|WI|WY|DC)(?:\s+\d{5}(?:-\d{4})?)?(?:\s*,?\s*(?:USA|US|United States))?\s*$"
)
US_PREFIX_STATE_RE = re.compile(
    r"\b(?:US|USA)[\s-]+(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b",
    re.I,
)
NON_US_CODE_RE = re.compile(r"(?:^|[,/])(?:DE|FR|IT|ES|NL|IN|BR|AU|SG|JP|ZA|MX|GB|UK|TW|TWN|BRA|PL|RO|IE|VN|PH|NZ|CH|BE|AT|SE|NO|DK|FI|IL|AE|SA|TH|MY|ID|PK|BD|UA|TR|EG|NG|GH|MA|PE|CR)-")
NON_US_LOCATION_RE = re.compile(
    r"\b(United Kingdom|UK|England|Canada|Toronto|Vancouver|"
    r"Poland|Romania|Spain|Barcelona|Italy|Milan|Torino|Brazil|Sao Paulo|São Paulo|"
    r"Belo Horizonte|Nairobi|Kenya|Philippines|Taguig|Vietnam|Singapore|India|Bengaluru|"
    r"Bangalore|Hyderabad|Pune|Mumbai|Chennai|Delhi|Noida|Gurugram|Gurgaon|Kolkata|"
    r"Bhubaneswar|Prague|Czech|Qatar|Doha|Ireland|Dublin|Netherlands|Amsterdam|"
    r"Germany|France|Paris|Mexico|Australia|Sydney|Taiwan|Taipei|Japan|Poland|"
    r"South Africa|Argentina|Chile|Colombia|Portugal|Switzerland|Belgium|Austria|"
    r"Sweden|Norway|Denmark|Finland|New Zealand|Israel|UAE|Dubai|Saudi Arabia|"
    r"Thailand|Malaysia|Indonesia|Pakistan|Bangladesh|Ukraine|Turkey|Cairo|Egypt|Nigeria|"
    r"Ghana|Morocco|Peru|Costa Rica|Brazil|TWN|BRA)\b",
    re.I,
)

EXPLICIT_ENTRY_TITLE_RE = re.compile(
    r"\b(new grad|new graduate|university grad|university graduate|college grad|"
    r"recent grad|early career|entry[- ]level|graduate software|junior|"
    r"software engineer\s*(i|1)\b|software development engineer\s*(i|1)\b|"
    r"software developer\s*(i|1)\b|backend engineer\s*(i|1)\b|"
    r"full[- ]?stack engineer\s*(i|1)\b|(?:ml|ai) engineer\s*(i|1)\b|"
    r"sde\s*(i|1)\b|engineer\s*(i|1)\b|associate software engineer|"
    r"member of technical staff|mts)\b",
    re.I,
)
FULL_TIME_HINT_RE = re.compile(r"\b(full[- ]time|regular|permanent)\b", re.I)
TITLE_DEFENSE_RE = re.compile(
    r"\b(defense|missile|payload|radar|spacecraft|flight software|top secret|ts/sci|public trust)\b",
    re.I,
)
DESCRIPTION_HARD_STOP_RE = re.compile(
    r"\b(itar|u\.s\. person|us person|security clearance|active clearance|top secret|ts/sci)\b",
    re.I,
)
DEFENSE_COMPANY_RE = re.compile(
    r"\b(anduril|spacex|rocketlab|trueanomaly|varda|cesiumastro|accenturefederalservices|"
    r"darkwolf|freedomconsulting|systemstechnologyresearch|morsecorp|questdefense)\b",
    re.I,
)
TIER_1_COMPANY_RE = re.compile(
    r"\b(google|alphabet|amazon|microsoft|meta|facebook|apple|nvidia|oracle|ibm|"
    r"salesforce|adobe|intel|cisco|uber|airbnb|doordash|stripe|block|paypal|"
    r"capitalone|capital one|jpmorgan|jp morgan|goldmansachs|goldman sachs|"
    r"bankofamerica|bank of america|walmart|target|costco|homedepot|home depot|"
    r"databricks|snowflake|servicenow|workday|atlassian|mongodb|cloudflare|"
    r"coinbase|roblox|reddit|pinterest|lyft|instacart|twilio|splunk|"
    r"doordashusa|robinhood|thenewyorktimes|new york times|esri|klaviyo)\b",
    re.I,
)
TIER_2_COMPANY_RE = re.compile(
    r"\b(samsara|elastic|clear|idme|lightningai|rdccareers|zoominfo|abnormalsecurity|"
    r"upstart|affirm|chime|mercury|fivetran|klaviyo|scaleai|grafanalabs|mozilla|"
    r"backblaze|sezzle|oura|nexhealth|figma|notion|brex|gitlab|github|"
    r"anthropic|openai|perplexity|linear|waymo)\b",
    re.I,
)

NO_EXPERIENCE_RE = re.compile(
    r"\b(no (?:professional |prior |previous )?experience (?:is )?required|"
    r"zero years? of (?:professional |relevant )?experience)\b",
    re.I,
)
YEARS_BEFORE_EXPERIENCE_RE = re.compile(
    r"\b(?P<low>\d{1,2})(?:\s*(?:-|–|—|to)\s*(?P<high>\d{1,2}))?\s*\+?\s*"
    r"years?\b.{0,100}?\bexperience\b",
    re.I | re.S,
)
EXPERIENCE_BEFORE_YEARS_RE = re.compile(
    r"\bexperience\b.{0,100}?\b(?P<low>\d{1,2})(?:\s*(?:-|–|—|to)\s*"
    r"(?P<high>\d{1,2}))?\s*\+?\s*years?\b",
    re.I | re.S,
)
OPEN_ENDED_TWO_PLUS_RE = re.compile(
    r"\b(?:"
    r"(?:2|[3-9]|[1-9]\d)\s*\+\s*years?|"
    r"(?:at least|minimum(?: of)?)\s+(?:2|[3-9]|[1-9]\d)\s+years?|"
    r"(?:2|[3-9]|[1-9]\d)\s+years?\s+(?:or more|minimum)"
    r")\b",
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
    experience: str | None = None
    dedupe_key: str | None = None


def as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_us_location(location: str | None) -> bool:
    if not location:
        return False
    if NON_US_LOCATION_RE.search(location) or NON_US_CODE_RE.search(location):
        return False
    return bool(US_LOCATION_RE.search(location) or US_STATE_SUFFIX_RE.search(location) or US_PREFIX_STATE_RE.search(location))


def has_us_url_signal(application_url: str | None) -> bool:
    if not application_url:
        return False
    path = application_url.split("?", 1)[0].split("#", 1)[0]
    parts = path.split("/")
    location_part = ""
    for index, part in enumerate(parts[:-1]):
        if part.casefold() == "job" and index + 1 < len(parts):
            location_part = parts[index + 1]
            break
    normalized = location_part.replace("-", " ").replace("_", " ")
    if re.search(r"\b(?:US|USA|United States)\b", normalized, re.I):
        return True
    if re.search(r"\b(?:US|USA)\b.{0,4}\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b", normalized, re.I):
        return True
    if re.search(
        r"\s(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
        r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)(?:\s|$)", normalized
    ):
        return True
    return bool(re.search(
        r"\b(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|"
        r"Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|"
        r"Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|"
        r"New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
        r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
        r"West Virginia|Wisconsin|Wyoming|District of Columbia)\b", normalized, re.I
    ))


def display_company(value: str) -> str:
    raw = (value or "").strip()
    parts = [part.strip() for part in raw.split("|") if part.strip()]
    if len(parts) > 1 and ".myworkdayjobs.com" in parts[0].casefold():
        raw = parts[-1] if parts[-1].casefold() not in {"external", "global", "careers", "jobs"} else parts[1]
        raw = raw.replace("_", " ").replace("-", " ")
    clean = re.sub(r"\s+", " ", raw).strip()
    special = {
        "capitalone": "Capital One", "bankofamerica": "Bank of America",
        "homedepot": "The Home Depot", "dxc technology": "DXC Technology",
        "dxc": "DXC Technology", "esri": "Esri", "t mobile": "T-Mobile",
        "newrelic": "New Relic", "purestorage": "Pure Storage",
        "analogdevices": "Analog Devices", "boozallenhamilton": "Booz Allen Hamilton",
        "state street": "State Street", "cloudflare": "Cloudflare",
    }
    return special.get(re.sub(r"[^a-z0-9 ]", "", clean.casefold()), clean.title())


def has_explicit_non_us_location(location: str | None, application_url: str | None = None) -> bool:
    if location and (NON_US_LOCATION_RE.search(location) or NON_US_CODE_RE.search(location)):
        return True
    if application_url:
        path = application_url.replace("-", " ").replace("_", " ")
        if NON_US_LOCATION_RE.search(path) or NON_US_CODE_RE.search(path):
            return True
    return False


def experience_label(text: str | None) -> str:
    if not text:
        return "Not stated"
    if NO_EXPERIENCE_RE.search(text):
        return "0 years"
    pattern = re.compile(
        r"\b(?P<low>\d{1,2})(?:\s*(?:-|–|—|to)\s*(?P<high>\d{1,2}))?\s*\+?\s*"
        r"years?\b.{0,100}?\bexperience\b|\bexperience\b.{0,100}?"
        r"\b(?P<low_after>\d{1,2})(?:\s*(?:-|–|—|to)\s*(?P<high_after>\d{1,2}))?\s*\+?\s*years?\b",
        re.I | re.S,
    )
    match = pattern.search(text)
    if not match:
        return "Not stated"
    low = int(match.group("low") or match.group("low_after"))
    high = int(match.group("high") or match.group("high_after") or low)
    if match.group(0).find("+") >= 0:
        return f"{low}+ years"
    return f"{low} year" if low == high == 1 else (f"{low} years" if low == high else f"{low}–{high} years")


def is_eligible_tech_title(title: str, description: str | None = None) -> bool:
    text_blob = f"{title}\n{description or ''}"
    if TITLE_DEFENSE_RE.search(title) or DESCRIPTION_HARD_STOP_RE.search(description or ""):
        return False
    if re.search(r"\b(member of technical staff|mts)\b", title, re.I):
        return True
    if EXCLUDE_TITLE_RE.search(title):
        return False
    return TECH_TITLE_RE.search(title) is not None


def is_entry_full_time_title(title: str, description: str | None = None) -> bool:
    return is_eligible_tech_title(title, description) and (
        EXPLICIT_ENTRY_TITLE_RE.search(title) is not None
    )


def extract_entry_experience(text: str | None) -> str | None:
    """Return posting-backed 0-2 year evidence, or None when it is absent/too senior."""
    if not text:
        return None
    # Check the full posting first. A lower requirement must never hide a second,
    # disqualifying requirement elsewhere in the qualifications list.
    if OPEN_ENDED_TWO_PLUS_RE.search(text):
        return None
    if NO_EXPERIENCE_RE.search(text):
        return "0 years"

    ranges: list[tuple[int, int]] = []
    spans: set[tuple[int, int]] = set()
    for pattern in (YEARS_BEFORE_EXPERIENCE_RE, EXPERIENCE_BEFORE_YEARS_RE):
        for match in pattern.finditer(text):
            if match.span() in spans:
                continue
            spans.add(match.span())
            low = int(match.group("low"))
            high = int(match.group("high") or low)
            context_start = max(0, match.start() - 30)
            context_end = min(len(text), match.end() + 20)
            context = text[context_start:context_end]
            open_ended = bool(
                re.search(r"\b(at least|minimum(?: of)?)\s*$", text[context_start:match.start()], re.I)
                or re.search(r"^\s*(?:\+|or more\b|minimum\b)", text[match.end():context_end], re.I)
                or (match.group("high") is None and re.search(rf"\b{low}\s*\+", match.group(0)))
                or re.search(rf"\b{low}\s+years?\s+(?:or more|minimum)\b", match.group(0), re.I)
            )
            if low >= 2 and open_ended:
                return None
            ranges.append((low, high))

    if not ranges or any(low > 2 or high > 2 for low, high in ranges):
        return None
    low = min(item[0] for item in ranges)
    high = max(item[1] for item in ranges)
    return f"{low} year" if low == high == 1 else (f"{low} years" if low == high else f"{low}–{high} years")


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
    if TIER_1_COMPANY_RE.search(job.company):
        return "Tier 1"
    if TIER_2_COMPANY_RE.search(job.company):
        return "Tier 2"
    return "Tier 3"


def fetch_jobs(since_hours: int, limit: int) -> list[EntryJob]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT coalesce(nullif(b.company_display, ''), registry.company_name, j.company) AS company,
                       j.title, j.location, j.date_posted, j.first_seen_at,
                       j.application_url, j.source, j.description_text,
                       coalesce(j.queue_key, j.canonical_url, j.application_url, j.external_id) AS dedupe_key
                FROM jobs j
                LEFT JOIN ats_boards b ON b.id = j.board_id
                LEFT JOIN LATERAL (
                    SELECT cr.company_name
                    FROM company_registry cr
                    WHERE cr.board_id = j.board_id
                    ORDER BY (cr.detection_status = 'detected') DESC, cr.priority, cr.company_name
                    LIMIT 1
                ) registry ON true
                WHERE j.first_seen_at > now() - (:hours * interval '1 hour')
                  AND j.application_url IS NOT NULL
                  AND j.expired_at IS NULL
                  AND coalesce(j.employment_type, 'unknown') IN ('full_time', 'unknown')
                ORDER BY j.first_seen_at DESC, j.date_posted DESC NULLS LAST
                """
            ),
            {"hours": since_hours},
        ).all()
    finally:
        db.close()

    jobs: list[EntryJob] = []
    seen_keys: set[str] = set()
    for company, title, location, date_posted, first_seen_at, application_url, source, description, dedupe_key in rows:
        if DEFENSE_COMPANY_RE.search(company):
            continue
        if has_explicit_non_us_location(location, application_url):
            continue
        if not is_eligible_tech_title(title, description):
            continue
        if not is_us_location(location) and not has_us_url_signal(application_url):
            continue
        key = str(dedupe_key or application_url or f"{company}:{title}:{location}")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        jobs.append(
            EntryJob(
                company=display_company(company),
                title=title,
                location=(location if is_us_location(location) else
                          "United States (from job link)" if has_us_url_signal(application_url) else
                          "⚠ Unknown location"),
                date_posted=as_aware(date_posted),
                first_seen_at=as_aware(first_seen_at) or datetime.now(timezone.utc),
                application_url=application_url,
                source=source,
                salary=extract_salary(description),
                experience=experience_label(description),
                dedupe_key=key,
            )
        )

    jobs.sort(
        key=lambda job: (
            job.date_posted or job.first_seen_at,
            job.first_seen_at,
        ),
        reverse=True,
    )
    return jobs if limit <= 0 else jobs[:limit]


def escape_cell(value: object) -> str:
    text_value = str(value or "").replace("\n", " ").strip()
    return text_value.replace("|", "\\|")


def format_time_ago(value: datetime, now: datetime | None = None) -> str:
    current = as_aware(now) or datetime.now(timezone.utc)
    observed = as_aware(value) or current
    seconds = max(0, int((current - observed).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def render_tier_table(jobs: list[EntryJob], now: datetime | None = None) -> list[str]:
    if not jobs:
        return ["No matching roles in this tier right now.", ""]

    lines = [
        "| Company | Role | Experience | Posted | Found | Salary | Apply |",
        "|---|---|---|---|---|---|---|",
    ]
    for job in jobs:
        apply = f"[Apply]({job.application_url})" if job.application_url else ""
        role = job.title
        if job.location:
            role = f"{role}<br><sub>{escape_cell(job.location)}</sub>"
        posted = (job.date_posted or job.first_seen_at).strftime("%Y-%m-%d")
        found = format_time_ago(job.first_seen_at, now)
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(job.company),
                    role.replace("|", "\\|"),
                    escape_cell(job.experience),
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


def render_markdown(
    jobs: list[EntryJob], since_hours: int, now: datetime | None = None
) -> str:
    generated_at = as_aware(now) or datetime.now(timezone.utc)
    generated_label = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    tiers: dict[str, list[EntryJob]] = defaultdict(list)
    for job in jobs:
        tiers[tier_for_job(job)].append(job)

    lines = [
        START_MARKER,
        "## Recent U.S. Technology Job Openings",
        "",
        f"Auto-updated hourly from CareerOS. Last run: **{generated_label}**. Showing U.S. software/AI/tech postings found in the last **7 days**.",
        "",
        f"Speed: CareerOS refreshes every hour from company career pages, then records the first time each posting was found. Current feed size: **{len(jobs)}** roles.",
        "",
        "Eligibility: recent software, AI/ML, data, infrastructure, security, embedded, and related engineering roles across experience levels. Internships, obvious non-technical roles, explicit non-U.S. postings, and defense/clearance-restricted roles are excluded. Unclear locations are marked for review.",
        "",
        "Quick links: [Tier 1](#tier-1) · [Tier 2](#tier-2) · [Tier 3](#tier-3)",
        "",
        "### Tier 1",
        "",
        "Large public and established technology, financial, and enterprise companies.",
        "",
        *render_tier_table(tiers["Tier 1"], generated_at),
        "### Tier 2",
        "",
        "Established mid-sized companies with meaningful engineering organizations.",
        "",
        *render_tier_table(tiers["Tier 2"], generated_at),
        "### Tier 3",
        "",
        "Startups, early-stage companies, and smaller technology businesses.",
        "",
        *render_tier_table(tiers["Tier 3"], generated_at),
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
    parser.add_argument("--limit", type=int, default=0, help="maximum rows; 0 publishes every matching role")
    args = parser.parse_args()

    jobs = fetch_jobs(args.since_hours, args.limit)
    block = render_markdown(jobs, args.since_hours)
    changed = update_readme(Path(args.readme), block)
    print(f"entry_jobs={len(jobs)} readme={args.readme} changed={changed}")


if __name__ == "__main__":
    main()
