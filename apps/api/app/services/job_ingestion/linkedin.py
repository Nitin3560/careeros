import os
from datetime import datetime
from typing import Any, Optional

import httpx


ACTOR_ID = "valig~linkedin-jobs-scraper"
API_BASE = "https://api.apify.com/v2"
DEFAULT_MAX_ITEMS = 400
DEFAULT_DATE_POSTED = "past24Hours"
DEFAULT_LOCATION = "United States"
TITLE_INCLUDE = [
    "software engineer",
    "software development engineer",
    "software developer",
    "backend engineer",
    "frontend engineer",
    "full stack engineer",
    "platform engineer",
    "infrastructure engineer",
    "site reliability engineer",
    "SRE",
    "DevOps engineer",
    "machine learning engineer",
    "ML engineer",
    "AI engineer",
    "applied scientist",
    "research engineer",
    "data engineer",
    "SDE",
    "SWE",
    "member of technical staff",
    "web developer",
    "application developer",
]
TITLE_EXCLUDE = [
    "sales engineer",
    "solutions engineer",
    "support engineer",
    "field engineer",
    "customer engineer",
    "implementation engineer",
    "pre-sales engineer",
    "partner engineer",
    "deployment engineer",
    "integration engineer",
    "technical account engineer",
    "mechanical engineer",
    "electrical engineer",
    "civil engineer",
    "hardware engineer",
    "firmware engineer",
    "staff",
    "principal",
    "director",
    "manager",
    "architect",
]
EXPERIENCE_LEVELS = ["entry", "associate", "mid"]


def fetch_linkedin_jobs(query_slug: str = "software-engineer") -> list[dict]:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("set APIFY_TOKEN to fetch LinkedIn jobs")

    query = query_slug.replace("-", " ").strip() or "software engineer"
    payload = build_actor_input(query)
    response = httpx.post(
        f"{API_BASE}/acts/{ACTOR_ID}/run-sync-get-dataset-items",
        params={"token": token, "clean": "true", "format": "json"},
        json=payload,
        timeout=180.0,
    )
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        return []

    return [job for item in items if (job := normalize_linkedin_item(item))]


def build_actor_input(query: str) -> dict:
    return {
        "query": query,
        "titleInclude": TITLE_INCLUDE,
        "titleExclude": TITLE_EXCLUDE,
        "experienceLevel": EXPERIENCE_LEVELS,
        "datePosted": DEFAULT_DATE_POSTED,
        "location": DEFAULT_LOCATION,
        "maxItems": DEFAULT_MAX_ITEMS,
        "proxy": {"useApifyProxy": True},
    }


def normalize_linkedin_item(item: dict[str, Any]) -> dict | None:
    job_id = _first(item, "id", "jobId", "job_id", "linkedinJobId", "link")
    title = _first(item, "title", "jobTitle", "position")
    if not job_id or not title:
        return None

    company = _first(item, "companyName", "company", "organization") or "linkedin"
    description = _description(item)
    return {
        "external_id": f"linkedin_{job_id}",
        "source": "linkedin",
        "company": str(company).lower(),
        "title": title,
        "location": _location(item),
        "description_text": description,
        "application_url": _first(item, "link", "url", "jobUrl", "applyUrl"),
        "date_posted": _parse_date(
            _first(item, "postedAt", "postedDate", "datePosted", "listedAt")
        ),
        "retrieved_at": datetime.utcnow(),
    }


def _description(item: dict[str, Any]) -> Optional[str]:
    parts = [
        _first(item, "description", "jobDescription", "descriptionText"),
        _first(item, "criteria", "seniorityLevel"),
        _first(item, "employmentType", "workplaceType"),
    ]
    return "\n\n".join(str(part) for part in parts if part) or None


def _location(item: dict[str, Any]) -> Optional[str]:
    value = _first(item, "location", "jobLocation", "formattedLocation")
    if isinstance(value, dict):
        return ", ".join(str(part) for part in value.values() if part) or None
    return value


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        value = value / 1000 if value > 10_000_000_000 else value
        return datetime.utcfromtimestamp(value)
    value = str(value).replace("Z", "+00:00")
    for parser in (
        datetime.fromisoformat,
        lambda raw: datetime.strptime(raw, "%Y-%m-%d"),
        lambda raw: datetime.strptime(raw, "%B %d, %Y"),
        lambda raw: datetime.strptime(raw, "%b %d, %Y"),
    ):
        try:
            parsed = parser(value)
            return parsed.replace(tzinfo=None)
        except ValueError:
            continue
    return None
