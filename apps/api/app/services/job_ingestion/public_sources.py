from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.services.job_ingestion.ashby import fetch_ashby_jobs
from app.services.job_ingestion.greenhouse import fetch_greenhouse_jobs
from app.services.job_ingestion.lever import fetch_lever_jobs

Fetcher = Callable[[str], list[dict]]


@dataclass(frozen=True)
class PublicSource:
    name: str
    slug: str
    source: str
    fetch: Fetcher


SOURCE_FETCHERS: dict[str, Fetcher] = {
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
    "ashby": fetch_ashby_jobs,
}


KNOWN_PUBLIC_SOURCES: dict[str, list[tuple[str, str]]] = {
    "cloudflare": [("greenhouse", "cloudflare")],
    "confluent": [("ashby", "confluent")],
    "datadog": [("greenhouse", "datadog")],
    "fastly": [("greenhouse", "fastly")],
    "gitlab": [("greenhouse", "gitlab")],
    "okta": [("greenhouse", "okta")],
    "snowflake": [("ashby", "snowflake")],
    "twilio": [("greenhouse", "twilio")],
    "zscaler": [("greenhouse", "zscaler")],
}


def discover_public_source(
    company_name: str, probe_unknown: bool = False
) -> PublicSource | None:
    company_key = normalize_company_key(company_name)
    candidates = KNOWN_PUBLIC_SOURCES.get(company_key)
    if candidates is None:
        if not probe_unknown:
            return None
        candidates = default_candidates(company_key)

    for source, slug in candidates:
        fetch = SOURCE_FETCHERS[source]
        try:
            jobs = fetch(slug)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 404}:
                continue
            continue
        except httpx.HTTPError:
            continue

        if jobs:
            return PublicSource(
                name=company_name,
                slug=slug,
                source=source,
                fetch=lambda _slug, _jobs=jobs: _jobs,
            )

    return None


def normalize_company_key(name: str) -> str:
    cleaned = name.lower().replace("&", "and")
    chars = [char if char.isalnum() else "-" for char in cleaned]
    return "-".join(part for part in "".join(chars).split("-") if part)


def default_candidates(company_key: str) -> list[tuple[str, str]]:
    compact = company_key.replace("-", "")
    return [
        ("greenhouse", compact),
        ("lever", compact),
        ("ashby", compact),
        ("greenhouse", company_key),
        ("lever", company_key),
        ("ashby", company_key),
    ]
