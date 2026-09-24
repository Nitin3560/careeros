import argparse
import re
import sys
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.classification.classifier import VERSION as CLASSIFIER_VERSION  # noqa: E402

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
    r"supervisor|technician|facilities|administrator|product design|designer|support|"
    r"customer|recruiter|engineer\s*(iii|3)\b|"
    r"software development engineer\s*(iii|3)\b|sde\s*(iii|3)\b|level\s*5)\b",
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
EXPLICIT_FOREIGN_RE = re.compile(
    r"\b(United Kingdom|UK|England|Scotland|Wales|Canada|India|Ireland|Germany|France|Spain|"
    r"Portugal|Italy|Netherlands|Belgium|Switzerland|Austria|Poland|Romania|Czech Republic|"
    r"Czechia|Australia|New Zealand|Singapore|Japan|China|Taiwan|Vietnam|Philippines|"
    r"Brazil|Mexico|Argentina|Chile|Colombia|Kenya|Nigeria|South Africa|Israel|Turkey|"
    r"Ukraine|Russia|Sweden|Norway|Denmark|Finland|Greece|Hungary|Serbia|Croatia|"
    r"Remote\s*[-–]\s*(?:EMEA|APAC|LATAM|Europe|Canada|India))\b", re.I,
)
US_STATE_CODE_END_RE = re.compile(
    r",\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|"
    r"VT|VA|WA|WV|WI|WY|DC)(?:\s+\d{5}(?:-\d{4})?)?\s*$"
)
FOREIGN_CITY_RE = re.compile(
    r"\b(Amsterdam|Barcelona|Milan|Nairobi|Noida|Taguig|Sao Paulo|São Paulo|Berlin|Munich|"
    r"Prague|Bengaluru|Bangalore|Hyderabad|Mumbai|Pune|Chennai|Delhi|Gurgaon|Madrid|Lisbon|"
    r"Zurich|Stockholm|Warsaw|Krakow|Dublin|Toronto|Vancouver|Montreal|Bogota|Medellin|"
    r"Buenos Aires|Belgrade|Manila|Jakarta|Tokyo|Sydney|Melbourne|Shanghai|Beijing|Shenzhen)\b",
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
    locations: tuple[str, ...] = ()
    is_new: bool = False
    is_aggregator: bool = False
    location_class: str = "unknown"


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


def has_explicit_non_us_location(location: str | None) -> bool:
    if not location:
        return False
    segments = re.split(r"\s*(?:;|\||/|\n)\s*", location)
    for segment in segments:
        has_us_signal = bool(
            US_STATE_CODE_END_RE.search(segment)
            or re.search(r",\s*(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming)\s*$", segment, re.I)
            or re.search(r"\b(?:United States|USA|US Remote|Remote\s*[-,]?\s*US)\b", segment, re.I)
        )
        if has_us_signal:
            continue
        if EXPLICIT_FOREIGN_RE.search(segment) or NON_US_LOCATION_RE.search(segment) or FOREIGN_CITY_RE.search(segment):
            return True
    return False


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
    # Only required qualifications count. Preferred experience is not a gate.
    headings = list(re.finditer(r"^##\s+(.+)$", text, flags=re.M))
    if headings:
        required_sections: list[str] = []
        for index, heading in enumerate(headings):
            name = heading.group(1).strip().rstrip(":").lower()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            if re.match(r"^(requirements?|qualifications?|minimum|basic qualifications?|required qualifications?|what we look for|what you bring|must have)$", name):
                required_sections.append(text[heading.end():end])
        text = " ".join(required_sections)
        if not text:
            return None
    text = _replace_number_words(text)
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


def _replace_number_words(text: str) -> str:
    number_words = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
                    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    return re.sub(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten)\b",
                  lambda match: number_words[match.group(0).lower()], text, flags=re.I)


def has_required_experience_evidence(text: str | None) -> bool:
    if not text:
        return False
    sections = list(re.finditer(r"^##\s+(.+)$", text, flags=re.M))
    if sections:
        required = []
        for index, heading in enumerate(sections):
            name = heading.group(1).strip().rstrip(":").lower()
            end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
            if re.match(r"^(requirements?|qualifications?|minimum|basic qualifications?|required qualifications?|what we look for|what you bring|must have)$", name):
                required.append(text[heading.end():end])
        text = " ".join(required)
    text = _replace_number_words(text)
    return bool(
        NO_EXPERIENCE_RE.search(text)
        or re.search(r"\b\d{1,2}\s*(?:-|–|—|to)\s*\d{1,2}\s*\+?\s*years?\b", text, re.I)
        or re.search(r"\b\d{1,2}\s*\+?\s*years?\b.{0,100}\bexperience\b|\bexperience\b.{0,100}\b\d{1,2}\s*\+?\s*years?\b", text, re.I | re.S)
    )


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


def company_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _dedupe_key(row) -> str:
    for value in (row["identity_key"], row["queue_key"], row["canonical_url"]):
        if value:
            return str(value).strip().lower()
    return str(row["application_url"] or "").split("?", 1)[0].rstrip("/").lower()


def collapse_duplicate_locations(jobs: list[EntryJob]) -> list[EntryJob]:
    grouped: dict[str, EntryJob] = {}
    for job in jobs:
        dedupe = job.dedupe_key or (job.application_url or "").split("?", 1)[0].rstrip("/").lower()
        if not dedupe:
            dedupe = f"unkeyed:{job.first_seen_at.isoformat()}"
        key = "::".join((company_key(job.company), re.sub(r"\s+", " ", job.title.casefold()).strip(), dedupe))
        previous = grouped.get(key)
        if previous is None:
            grouped[key] = job
            continue
        locations = list(previous.locations or ((previous.location,) if previous.location else ()))
        locations.extend(job.locations or ((job.location,) if job.location else ()))
        clean_locations = tuple(dict.fromkeys(item.strip() for item in locations if item and item.strip()))
        grouped[key] = EntryJob(
            **{**previous.__dict__, "locations": clean_locations,
               "is_new": previous.is_new or job.is_new,
               "is_aggregator": previous.is_aggregator or job.is_aggregator,
               "location_class": "unknown" if "unknown" in {previous.location_class, job.location_class} else previous.location_class}
        )
    return list(grouped.values())


def fetch_jobs(since_hours: int, limit: int) -> list[EntryJob]:
    from sqlalchemy import text
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT coalesce(reg.company_name, nullif(b.company_display, ''),
                                nullif(b.company_name, ''), j.company) AS company,
                       (reg.company_name IS NOT NULL OR nullif(b.company_display, '') IS NOT NULL OR nullif(b.company_name, '') IS NOT NULL) AS company_is_verified,
                       j.title, j.location, j.date_posted, j.first_seen_at,
                       j.application_url, j.source, j.description_text,
                       j.identity_key, j.queue_key, j.canonical_url,
                       j.is_new_grad_title, j.min_years_required,
                       j.location_class,
                       rule.rule = 'aggregator' AS is_aggregator,
                       state.last_viewed_at
                FROM jobs j
                LEFT JOIN ats_boards b ON b.id = j.board_id
                LEFT JOIN LATERAL (
                    SELECT cr.company_name
                    FROM company_registry cr
                    WHERE cr.detection_status = 'detected'
                      AND (cr.board_id = b.id OR lower(cr.company_name) IN (lower(coalesce(b.company_display, '')), lower(coalesce(b.company_name, '')), lower(j.company)))
                    ORDER BY (cr.board_id = b.id) DESC, cr.priority ASC, cr.company_name
                    LIMIT 1
                ) reg ON true
                LEFT JOIN job_feed_company_rules rule
                  ON rule.company_key = regexp_replace(lower(coalesce(reg.company_name, nullif(b.company_display, ''), nullif(b.company_name, ''), j.company)), '[^a-z0-9]', '', 'g')
                CROSS JOIN job_feed_state state
                WHERE j.first_seen_at > now() - (:hours * interval '1 hour')
                  AND j.application_url IS NOT NULL
                  AND j.expired_at IS NULL
                  AND j.classifier_version = :classifier_version
                  AND j.is_tech_title IS TRUE
                  AND j.is_senior_title IS FALSE
                  AND j.employment_type = 'full_time'
                  AND j.location_class IN ('us', 'unknown')
                  AND coalesce(j.sponsorship_block, false) IS FALSE
                  AND (j.min_years_required IS NULL OR j.min_years_required <= 2)
                  AND (rule.rule IS NULL OR rule.rule = 'aggregator')
                ORDER BY j.first_seen_at DESC, j.date_posted DESC NULLS LAST
                LIMIT 20000
                """
            ),
            {"hours": since_hours, "classifier_version": CLASSIFIER_VERSION},
        ).mappings().all()
    finally:
        db.close()

    jobs: list[EntryJob] = []
    for row in rows:
        company = row["company"]
        title = row["title"]
        description = row["description_text"]
        if not row["company_is_verified"]:
            continue
        if not markdown_apply_link(row["application_url"]):
            continue
        if DEFENSE_COMPANY_RE.search(company) or TITLE_DEFENSE_RE.search(title):
            continue
        if has_explicit_non_us_location(row["location"]):
            continue
        experience = extract_entry_experience(description)
        if experience is None:
            if row["min_years_required"] is not None or has_required_experience_evidence(description):
                # A parsed required-years value with no safe <=2-year interpretation
                # means open-ended/conflicting evidence; do not relabel it as unstated.
                continue
            # Classifier-approved early-career records without explicit years remain visible,
            # but are labeled honestly rather than presented as verified 0-2 year roles.
            experience = "New grad" if row["is_new_grad_title"] else "Not stated"
        if row["min_years_required"] is not None and row["min_years_required"] > 2:
            continue
        key = _dedupe_key(row)
        viewed_at = as_aware(row["last_viewed_at"])
        found_at = as_aware(row["first_seen_at"]) or datetime.now(timezone.utc)
        location = row["location"]
        jobs.append(
            EntryJob(
                company=company,
                title=title,
                location=location,
                date_posted=as_aware(row["date_posted"]),
                first_seen_at=found_at,
                application_url=row["application_url"],
                source=row["source"],
                salary=extract_salary(description),
                experience=experience,
                dedupe_key=key,
                locations=(location,) if location else (),
                is_new=bool(viewed_at and found_at > viewed_at),
                is_aggregator=bool(row["is_aggregator"]),
                location_class=row["location_class"] or "unknown",
            )
        )

    jobs = collapse_duplicate_locations(jobs)
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
    text_value = text_value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|])", r"\\\1", text_value)


def markdown_apply_link(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return ""
        hostname = parsed.hostname
        if ":" in hostname:
            if not re.fullmatch(r"[0-9a-fA-F:]+", hostname):
                return ""
            hostname = f"[{hostname}]"
        elif not re.fullmatch(r"[A-Za-z0-9.-]+", hostname):
            return ""
        port = parsed.port
        netloc = hostname.lower() + (f":{port}" if port else "")
        path = quote(parsed.path, safe="/%:@!$&'*,;=+-._~")
        query = quote(parsed.query, safe="/?@!$&'*,;=+-._~")
        safe_url = urlunsplit((parsed.scheme.lower(), netloc, path, query, "")).replace(")", "%29")
        return f"[Apply]({safe_url})"
    except ValueError:
        return ""


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

    lines: list[str] = []
    grouped: dict[str, list[EntryJob]] = defaultdict(list)
    for job in jobs:
        grouped[(job.date_posted or job.first_seen_at).strftime("%Y-%m-%d")].append(job)
    for day, day_jobs in sorted(grouped.items(), reverse=True):
        lines.extend([f"#### {day}", "", "| Company | Role | Location | Experience | Posted | Found | Salary | Apply |", "|---|---|---|---|---|---|---|---|"])
        for job in day_jobs:
            locations = job.locations or ((job.location,) if job.location else ())
            location_label = "; ".join(locations[:5])
            if len(locations) > 5:
                location_label += f"; +{len(locations) - 5} more"
            if not location_label or job.location_class == "unknown":
                location_label = "⚠ Unknown location"
            company_label = escape_cell(job.company)
            if job.is_aggregator:
                company_label += " *(Second-hand)*"
            role = escape_cell(job.title) + (" **NEW**" if job.is_new else "")
            apply = markdown_apply_link(job.application_url)
            posted = job.date_posted.strftime("%Y-%m-%d") if job.date_posted else "Not shown"
            found = format_time_ago(job.first_seen_at, now)
            lines.append(
                "| " + " | ".join([
                    company_label, role, escape_cell(location_label),
                    escape_cell(job.experience), escape_cell(posted), escape_cell(found), escape_cell(job.salary), apply,
                ]) + " |"
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
        "## New Grad & Entry-Level Engineering Roles",
        "",
        f"Auto-updated hourly from classified CareerOS postings. Last run: **{generated_label}**. Showing active roles found in the last **7 days**.",
        "",
        f"Speed: CareerOS refreshes every hour from company career pages, then records the first time each posting was found. Current feed size: **{len(jobs)}** roles.",
        "",
        "Eligibility: current-version classifier-approved full-time technology roles in the U.S. Explicitly non-U.S., senior, restricted, expired, blocked-company, and over-two-year roles are excluded. Unknown locations and unstated experience are labeled for review.",
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

    if START_MARKER in content or END_MARKER in content:
        if content.count(START_MARKER) != 1 or content.count(END_MARKER) != 1 or content.index(START_MARKER) > content.index(END_MARKER):
            raise ValueError("README feed markers must occur exactly once and in start/end order")
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

    if args.since_hours < 1 or args.limit < 1:
        parser.error("since-hours and limit must be positive")

    jobs = fetch_jobs(args.since_hours, args.limit)
    block = render_markdown(jobs, args.since_hours)
    changed = update_readme(Path(args.readme), block)
    print(f"entry_jobs={len(jobs)} readme={args.readme} changed={changed}")


if __name__ == "__main__":
    main()
