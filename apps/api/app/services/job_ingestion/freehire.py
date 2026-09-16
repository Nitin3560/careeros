from datetime import datetime
import os
from typing import Any

import httpx


DEFAULT_BASE_URL = "https://freehire.me"


def fetch_freehire_jobs(query: str = "software engineer") -> list[dict]:
    params = {
        "q": query.replace("-", " "),
        "limit": 50,
        "offset": 0,
        "semantic_ratio": 0,
        "include_description": "true",
        "description_format": "markdown",
        "posted_within_days": 14,
    }
    response = httpx.get(
        f"{base_url()}/api/v1/agent/jobs/search",
        params=params,
        timeout=15.0,
    )
    response.raise_for_status()
    payload = response.json()
    return [_normalize_job(item) for item in payload.get("results", [])]


def base_url() -> str:
    return os.getenv("FREEHIRE_API_URL", DEFAULT_BASE_URL).rstrip("/")


def _normalize_job(item: dict[str, Any]) -> dict:
    job_id = (
        item.get("id")
        or item.get("public_slug")
        or item.get("external_id")
        or item.get("url")
    )
    company = _company_name(item)
    return {
        "external_id": f"freehire_{job_id}",
        "source": "freehire",
        "company": company,
        "title": item.get("title"),
        "location": item.get("location") or _join_location(item),
        "description_text": item.get("description"),
        "application_url": item.get("url"),
        "date_posted": _parse_date(item.get("posted_at") or item.get("created_at")),
        "retrieved_at": datetime.utcnow(),
    }


def _company_name(item: dict[str, Any]) -> str:
    company = item.get("company")
    if isinstance(company, dict):
        return company.get("name") or company.get("slug") or "unknown"
    return company or item.get("company_slug") or "unknown"


def _join_location(item: dict[str, Any]) -> str | None:
    parts = []
    for key in ("cities", "regions", "countries"):
        value = item.get(key)
        if isinstance(value, list):
            parts.extend(str(part) for part in value if part)
        elif value:
            parts.append(str(value))
    return ", ".join(parts) or None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
