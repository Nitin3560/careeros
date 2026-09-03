from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.services.job_ingestion.ashby import fetch_ashby_jobs
from app.services.job_ingestion.amazon import fetch_amazon_jobs
from app.services.job_ingestion.greenhouse import fetch_greenhouse_jobs
from app.services.job_ingestion.lever import fetch_lever_jobs
from app.services.job_ingestion.linkedin import fetch_linkedin_jobs
from app.services.job_ingestion.smartrecruiters import fetch_smartrecruiters_jobs
from app.services.job_ingestion.workable import fetch_workable_jobs

Fetcher = Callable[[str], list[dict]]


@dataclass(frozen=True)
class PublicSource:
    name: str
    slug: str
    source: str
    fetch: Fetcher


SOURCE_FETCHERS: dict[str, Fetcher] = {
    "amazon": fetch_amazon_jobs,
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
    "linkedin": fetch_linkedin_jobs,
    "ashby": fetch_ashby_jobs,
    "smartrecruiters": fetch_smartrecruiters_jobs,
    "workable": fetch_workable_jobs,
}


KNOWN_PUBLIC_SOURCES: dict[str, list[tuple[str, str]]] = {
    "amazon": [("amazon", "software-development-engineer")],
    "arista-networks": [("smartrecruiters", "aristanetworks")],
    "cloudflare": [("greenhouse", "cloudflare")],
    "confluent": [("ashby", "confluent")],
    "datadog": [("greenhouse", "datadog")],
    "fastly": [("greenhouse", "fastly")],
    "gitlab": [("greenhouse", "gitlab")],
    "okta": [("greenhouse", "okta")],
    "servicenow": [("smartrecruiters", "servicenow")],
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
    slugs = slug_variants(company_key)
    sources = ["greenhouse", "lever", "ashby", "smartrecruiters", "workable"]
    return [(source, slug) for slug in slugs for source in sources]


def slug_variants(company_key: str) -> list[str]:
    suffixes = {
        "co",
        "company",
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "labs",
        "platforms",
        "technologies",
        "technology",
    }
    parts = company_key.split("-")
    without_suffixes = "-".join(part for part in parts if part not in suffixes)

    variants = [
        company_key.replace("-", ""),
        company_key,
        without_suffixes.replace("-", ""),
        without_suffixes,
        f"{company_key}inc",
        f"{company_key}-inc",
    ]

    seen = set()
    return [slug for slug in variants if slug and not (slug in seen or seen.add(slug))]
