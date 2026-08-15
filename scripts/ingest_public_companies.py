import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))
load_dotenv(API_DIR / ".env")

from app.database import SessionLocal  # noqa: E402
from app.services.job_ingestion.persist import save_jobs  # noqa: E402
from app.services.job_ingestion.public_sources import discover_public_source  # noqa: E402

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe-unknown", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    companies = args.company or DEFAULT_COMPANIES
    db = SessionLocal()
    results = []

    try:
        for company in companies:
            source = discover_public_source(company, probe_unknown=args.probe_unknown)
            if not source:
                results.append({"company": company, "status": "no_public_source_found"})
                continue

            jobs = source.fetch(source.slug)
            save_result = {"inserted": 0, "skipped": 0}
            if not args.dry_run:
                save_result = save_jobs(db, jobs)

            results.append(
                {
                    "company": company,
                    "source": source.source,
                    "slug": source.slug,
                    "fetched": len(jobs),
                    **save_result,
                }
            )
    finally:
        db.close()

    payload = {
        "companies_requested": len(companies),
        "companies_with_public_source": sum(
            1 for result in results if result.get("source")
        ),
        "total_fetched": sum(result.get("fetched", 0) for result in results),
        "total_inserted": sum(result.get("inserted", 0) for result in results),
        "total_skipped": sum(result.get("skipped", 0) for result in results),
        "results": results,
    }

    text = json.dumps(payload, indent=2)
    print(text)
    if args.output:
        output = ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n")


if __name__ == "__main__":
    main()
