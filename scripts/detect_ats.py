#!/usr/bin/env python3
"""Detect and verify ATS boards for company_registry rows."""
import argparse
import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

import httpx
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402
from app.ingestion.registry_detection import find_ats, verify_match  # noqa: E402

USER_AGENT = "CareerOS-Registry-Detector/1.0 (+https://github.com/Nitin3560/careeros)"


async def playwright_urls(url: str) -> list[str]:
    from playwright.async_api import async_playwright
    captured = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("request", lambda request: captured.append(request.url))
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(10000)
        await browser.close()
    return captured


async def detect_one(client, semaphore, row, use_playwright=False):
    if not row["careers_url"]:
        return row, None, "not_found", "low", "missing careers_url"
    try:
        async with semaphore:
            response = await client.get(row["careers_url"])
        response.raise_for_status()
        chain = [str(item.url) for item in response.history]
        redirect_chain = " -> ".join([*chain, str(response.url)])
        match = find_ats(chain, str(response.url), response.text)
        if match is None and use_playwright:
            async with semaphore:
                network_urls = await playwright_urls(str(response.url))
            match = find_ats(chain, str(response.url), response.text, network_urls)
        if match is None:
            return row, None, "not_found", "low", redirect_chain
        evidence = f"{match.evidence}; redirect_chain={redirect_chain}"
        if not match.supported:
            return row, match, "unsupported", "high", evidence
        async with semaphore:
            verified = await verify_match(client, match)
        if not verified:
            return row, match, "error", "low", f"verification failed: {evidence}"
        return row, match, "detected", "high", evidence
    except Exception as exc:
        return row, None, "error", "low", f"{type(exc).__name__}: {exc}"[:1000]


def persist_result(db, row, match, status, confidence, evidence):
    board_id = None
    if status == "detected" and match and match.supported:
        board_id = db.execute(text("""
            SELECT id FROM ats_boards WHERE ats=:ats AND slug=:slug
        """), {"ats": match.ats, "slug": match.slug}).scalar_one_or_none()
        if board_id is None:
            board_id = uuid.uuid4()
            db.execute(text("""
                INSERT INTO ats_boards
                    (id, ats, slug, company_name, status, tier, priority, source_list,
                     poll_interval_seconds, next_poll_at, consecutive_failures,
                     not_found_count, created_at, updated_at)
                VALUES (:id, :ats, :slug, :company, 'unknown', 'B', :priority,
                        'registry', 3600, now(), 0, 0, now(), now())
            """), {"id": board_id, "ats": match.ats, "slug": match.slug,
                     "company": row["company_name"], "priority": row["priority"]})
    db.execute(text("""
        UPDATE company_registry SET detected_ats=:ats, detected_slug=:slug,
            workday_host=:host, workday_tenant=:tenant, workday_site=:site,
            detection_status=:status, detection_confidence=:confidence,
            detection_evidence=:evidence, board_id=:board_id,
            last_detected_at=now(), updated_at=now() WHERE id=:id
    """), {
        "ats": match.ats if match else None, "slug": match.slug if match else None,
        "host": match.workday_host if match else None,
        "tenant": match.workday_tenant if match else None,
        "site": match.workday_site if match else None,
        "status": status, "confidence": confidence, "evidence": evidence,
        "board_id": board_id, "id": row["id"],
    })


async def run(args):
    db = SessionLocal()
    try:
        rows = [dict(row) for row in db.execute(text("""
            SELECT id, company_name, careers_url, priority FROM company_registry
            WHERE detection_status IN ('pending','error')
               OR last_detected_at < now()-interval '30 days'
            ORDER BY priority, company_name LIMIT :limit
        """), {"limit": args.limit}).mappings().all()]
        semaphore = asyncio.Semaphore(8)
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            results = await asyncio.gather(*(detect_one(client, semaphore, row, args.playwright) for row in rows))
        for result in results:
            persist_result(db, *result)
        db.commit()
        summary = {}
        for _row, match, status, _confidence, _evidence in results:
            key = (match.ats if match else "none", status)
            summary[key] = summary.get(key, 0) + 1
        for (ats, status), count in sorted(summary.items()):
            print(f"ats={ats} status={status} count={count}")
        review = Path(args.review_csv)
        review.parent.mkdir(parents=True, exist_ok=True)
        with review.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("company_name", "careers_url", "status", "detected_ats", "evidence"))
            for row, match, status, _confidence, evidence in results:
                if status in {"not_found", "unsupported"}:
                    writer.writerow((row["company_name"], row["careers_url"], status, match.ats if match else "", evidence))
        print(f"review_csv={review}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000000)
    parser.add_argument("--playwright", action="store_true")
    parser.add_argument("--review-csv", default=str(ROOT / "reports" / "ats_detection_review.csv"))
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
