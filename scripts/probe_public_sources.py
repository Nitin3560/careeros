import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from app.services.job_ingestion.public_sources import (  # noqa: E402
    KNOWN_PUBLIC_SOURCES,
    default_candidates,
    normalize_company_key,
)

DEFAULT_COMPANIES = [
    "Apple",
    "Microsoft",
    "Alphabet (Google)",
    "Amazon",
    "Meta Platforms",
    "IBM",
    "Oracle",
    "Tesla",
    "NVIDIA",
    "Intel",
    "AMD",
    "Qualcomm",
    "Broadcom",
    "TSMC",
    "Micron Technology",
    "Texas Instruments",
    "Marvell Technology",
    "GlobalFoundries",
    "Samsung Electronics",
    "Sony",
    "Dell Technologies",
    "HP Inc.",
    "Lenovo",
    "ASUS",
    "Acer",
    "Cisco",
    "Juniper Networks",
    "Arista Networks",
    "Palo Alto Networks",
    "CrowdStrike",
    "Zscaler",
    "Okta",
    "Fortinet",
    "Check Point",
    "Salesforce",
    "Adobe",
    "ServiceNow",
    "Workday",
    "Atlassian",
    "SAP",
    "Snowflake",
    "Zoom",
    "Twilio",
    "GitHub",
    "GitLab",
    "HashiCorp",
    "Datadog",
    "Cloudflare",
    "Fastly",
    "Confluent",
]


def probe_candidate(client: httpx.Client, source: str, slug: str) -> int:
    if source == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        data = client.get(url).json()
        return len(data.get("jobs", []))

    if source == "lever":
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        data = client.get(url).json()
        return len(data if isinstance(data, list) else [])

    if source == "ashby":
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        data = client.get(url).json()
        return len(data.get("jobs", []))

    return 0


def probe_company(company: str, timeout: float) -> dict:
    key = normalize_company_key(company)
    candidates = KNOWN_PUBLIC_SOURCES.get(key, default_candidates(key))

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for source, slug in candidates:
            try:
                count = probe_candidate(client, source, slug)
            except httpx.HTTPError:
                continue
            except (KeyError, TypeError, ValueError):
                continue

            if count:
                return {
                    "company": company,
                    "status": "found",
                    "source": source,
                    "slug": slug,
                    "job_count": count,
                }

    return {"company": company, "status": "not_found"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", action="append")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--output", default="reports/job-pool-probe.json")
    args = parser.parse_args()

    companies = args.company or DEFAULT_COMPANIES
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(probe_company, company, args.timeout): company
            for company in companies
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item["company"].lower())
    found = [result for result in results if result["status"] == "found"]
    payload = {
        "companies_requested": len(companies),
        "companies_with_public_source": len(found),
        "total_jobs_available": sum(result.get("job_count", 0) for result in found),
        "results": results,
    }

    text = json.dumps(payload, indent=2)
    print(text)

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n")


if __name__ == "__main__":
    main()
