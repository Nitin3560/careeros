#!/usr/bin/env python3
"""Detect and verify ATS boards for company_registry rows."""
import argparse
import asyncio
import csv
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlparse
import uuid

import httpx
from lxml import html as lxml_html
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402
from app.ingestion.registry_detection import ATSMatch, find_ats, verify_match  # noqa: E402
from app.ingestion.poller.fetcher import AsyncBoardFetcher  # noqa: E402

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
DISCOVERY_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "From": "https://github.com/Nitin3560/careeros",
}
BLOCKED_STATUSES = {403, 429, 503}
KNOWN_BOARDS_SQL = """
    SELECT b.ats, b.slug, b.company_name, r.adapter_config
    FROM ats_boards AS b
    LEFT JOIN company_registry AS r ON r.board_id = b.id
    WHERE b.status <> 'dead'
"""
CAREER_LINK = re.compile(r"careers|jobs|join|work\s*with\s*us|open\s*roles", re.I)
CAREER_PATH = re.compile(r"/(?:[^/?#]*(?:careers|jobs|join|open(?:ings|[-_ ]?roles?))[^/?#]*)", re.I)
EXCLUDED_PATH = re.compile(r"/(?:press|news|blog|about|investor)(?:/|$)", re.I)
KNOWN_ATS_HOSTS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com",
    "smartrecruiters.com", "icims.com", "workable.com", "bamboohr.com",
    "applytojob.com", "recruitee.com", "breezy.hr", "teamtailor.com",
    "eightfold.ai", "phenom.com", "successfactors.com", "oraclecloud.com",
    "taleo.net", "avature.net", "rippling.com", "paylocity.com",
)


def careers_candidates(domain: str) -> list[str]:
    domain = domain.strip().lower().strip("/")
    base = [
        f"https://{domain}/careers",
        f"https://{domain}/jobs",
        f"https://careers.{domain}",
        f"https://jobs.{domain}",
        f"https://www.{domain}/careers",
        f"https://www.{domain}/jobs",
        f"https://{domain}",
    ]
    return base + [
        f"https://{domain}/about/careers",
        f"https://{domain}/company/careers",
        f"https://{domain}/company/jobs",
        f"https://{domain}/join",
        f"https://{domain}/join-us",
        f"https://{domain}/work-with-us",
        f"https://{domain}/careers/jobs",
        f"https://{domain}/en/careers",
        f"https://{domain}/careers/open-positions",
    ]


async def playwright_page(url: str):
    from playwright.async_api import async_playwright
    captured = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=BROWSER_USER_AGENT, viewport={"width": 1440, "height": 1000},
            locale="en-US",
        )
        page = await context.new_page()
        page.on("request", lambda request: captured.append(request.url))
        response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(10000)
        result = {
            "url": page.url, "html": await page.content(), "network_urls": captured,
            "status_code": response.status if response else None,
        }
        await browser.close()
    return result


def _diagnostic(url, response=None, exc=None, *, playwright=False):
    history = [str(item.url) for item in response.history] if response is not None else []
    final_url = str(response.url) if response is not None else url
    return {
        "url": url,
        "final_status_code": response.status_code if response is not None else None,
        "redirect_chain": [*history, final_url],
        "exception_type": type(exc).__name__ if exc else None,
        "response_size": len(response.content) if response is not None else 0,
        "playwright": playwright,
    }


async def probe_url(client, global_semaphore, domain_semaphores, domain, url, playwright_loader=playwright_page, playwright_budget=None):
    domain_semaphore = domain_semaphores.setdefault(domain, asyncio.Semaphore(3))
    try:
        async with global_semaphore, domain_semaphore:
            response = await client.get(url)
        diagnostic = _diagnostic(url, response)
        if response.status_code not in BLOCKED_STATUSES:
            return {
                "url": str(response.url), "html": response.text if response.is_success else "",
                "network_urls": [], "response": response,
            }, [diagnostic]
        trigger = httpx.HTTPStatusError("blocked", request=response.request, response=response)
    except Exception as exc:
        response = None
        trigger = exc
        diagnostic = _diagnostic(url, exc=exc)
    if playwright_budget is not None and playwright_budget[0] >= 3:
        return None, [diagnostic]
    if playwright_budget is not None:
        playwright_budget[0] += 1
    try:
        async with global_semaphore, domain_semaphore:
            rendered = await playwright_loader(url)
        rendered_response = httpx.Response(
            rendered.get("status_code") or 200,
            request=httpx.Request("GET", url),
            text=rendered.get("html") or "",
        )
        browser_diag = _diagnostic(url, rendered_response, playwright=True)
        browser_diag["redirect_chain"] = [url, rendered.get("url") or url]
        return {
            "url": rendered.get("url") or url, "html": rendered.get("html") or "",
            "network_urls": rendered.get("network_urls") or [], "response": rendered_response,
        }, [diagnostic, browser_diag]
    except Exception as browser_exc:
        browser_diag = _diagnostic(url, exc=browser_exc, playwright=True)
        browser_diag["fallback_for"] = type(trigger).__name__
        return None, [diagnostic, browser_diag]


def first_career_link(markup: str, base_url: str, domain: str) -> str | None:
    try:
        root = lxml_html.fromstring(markup or "<html></html>")
    except (TypeError, ValueError):
        return None
    for anchor in root.xpath("//a[@href]"):
        href = anchor.get("href") or ""
        target = urljoin(base_url, href)
        parsed = urlparse(target)
        path = parsed.path or "/"
        # Use the URL path as the signal. Anchor text alone can be a job title.
        if not CAREER_PATH.search(path) or EXCLUDED_PATH.search(path):
            continue
        host = (urlparse(target).hostname or "").lower()
        if host == domain or host.endswith(f".{domain}") or any(host.endswith(ats) for ats in KNOWN_ATS_HOSTS):
            return target
    return None


def sitemap_career_urls(markup: str) -> list[str]:
    values = re.findall(r"<loc>\s*(.*?)\s*</loc>", markup or "", flags=re.I | re.S)
    return [value.strip() for value in values if CAREER_LINK.search(value)]


async def detect_one(
    client, semaphore, domain_semaphores, row, use_playwright=False,
    playwright_loader=playwright_page, known_boards=None, poller_fetcher=None,
):
    row["_attempt_diagnostics"] = []
    row["_company_started_at"] = time.monotonic()
    playwright_budget = [0]
    try:
        domain = (row.get("domain") or urlparse(row.get("careers_url") or "").hostname or "").lower()
        if not domain:
            return row, None, "not_found", "low", "missing careers_url and domain"
        candidates = [row["careers_url"]] if row.get("careers_url") else careers_candidates(domain)
        seen = set()
        homepage_page = None
        match = None
        chosen_page = None
        chosen_candidate = None

        async def inspect(candidate):
            nonlocal homepage_page
            if not candidate or candidate in seen:
                return None, None
            seen.add(candidate)
            page, diagnostics = await probe_url(
                client, semaphore, domain_semaphores, domain, candidate, playwright_loader,
                playwright_budget=playwright_budget,
            )
            row["_attempt_diagnostics"].extend(diagnostics)
            if candidate.rstrip("/") == f"https://{domain}".rstrip("/") and page:
                homepage_page = page
            if not page:
                return None, None
            chain = diagnostics[-1]["redirect_chain"]
            found = find_ats(chain[:-1], page["url"], page["html"], page["network_urls"])
            if found:
                row["_partial_match"] = found
            if found or not use_playwright or diagnostics[-1].get("playwright"):
                return found, page
            if playwright_budget[0] >= 3:
                return None, page
            playwright_budget[0] += 1
            try:
                async with semaphore, domain_semaphores.setdefault(domain, asyncio.Semaphore(3)):
                    rendered = await playwright_loader(page["url"])
                rendered_response = httpx.Response(
                    rendered.get("status_code") or 200,
                    request=httpx.Request("GET", page["url"]), text=rendered.get("html") or "",
                )
                browser_diag = _diagnostic(page["url"], rendered_response, playwright=True)
                browser_diag["redirect_chain"] = [page["url"], rendered.get("url") or page["url"]]
                row["_attempt_diagnostics"].append(browser_diag)
                found = find_ats(
                    [page["url"]], rendered.get("url") or page["url"],
                    rendered.get("html") or "", rendered.get("network_urls") or [],
                )
                return found, {**page, **rendered}
            except Exception as exc:
                row["_attempt_diagnostics"].append(_diagnostic(page["url"], exc=exc, playwright=True))
                return None, page

        for candidate in candidates:
            match, chosen_page = await inspect(candidate)
            if match:
                chosen_candidate = candidate
                break

        if match is None and homepage_page:
            link = first_career_link(homepage_page["html"], homepage_page["url"], domain)
            if link:
                match, chosen_page = await inspect(link)
                chosen_candidate = link if match else None

        if match is not None:
            # Verify immediately; this avoids probing remaining candidates.
            async with semaphore:
                verified = await verify_match(client, match, poller_fetcher)
            diagnostics_json = json.dumps(row.get("_attempt_diagnostics", []), separators=(",", ":"))
            evidence = f"discovered_careers_url={chosen_page['url'] if chosen_page else row.get('careers_url')}; {match.evidence}; diagnostics={diagnostics_json}"
            if not verified:
                return row, match, "error", "low", f"verification failed: {evidence}"
            row["careers_url"] = chosen_page["url"] if chosen_page else row.get("careers_url")
            return row, match, "detected", "high", evidence

        # Some companies expose no ATS fingerprint on their marketing site,
        # but already have a verified board (for example greenhouse/anthropic).
        # Re-verify a slug that matches the domain or company name before
        # declaring the registry row missing.
        if match is None and known_boards:
            tokens = {re.sub(r"[^a-z0-9]", "", value.lower()) for value in (
                domain.split(".")[0], row.get("company_name", ""),
            ) if value}
            for board in known_boards:
                slug_token = re.sub(r"[^a-z0-9]", "", str(board["slug"]).split("|")[0].lower())
                company_token = re.sub(r"[^a-z0-9]", "", str(board.get("company_name") or "").lower())
                if not ({slug_token, company_token} & tokens):
                    continue
                candidate = ATSMatch(
                    board["ats"], board["slug"], "existing ats_boards fallback",
                    endpoint_params=board.get("adapter_config") or {},
                )
                if await verify_match(client, candidate, poller_fetcher):
                    match = candidate
                    chosen_candidate = f"ats_boards:{board['ats']}/{board['slug']}"
                    chosen_page = {"url": row.get("careers_url") or f"https://{domain}", "html": "", "network_urls": []}
                    break

        if match is None:
            sitemap_url = f"https://{domain}/sitemap.xml"
            sitemap_page, sitemap_diagnostics = await probe_url(
                client, semaphore, domain_semaphores, domain, sitemap_url, playwright_loader
            )
            row["_attempt_diagnostics"].extend(sitemap_diagnostics)
            if sitemap_page:
                for link in sitemap_career_urls(sitemap_page["html"])[:50]:
                    match, chosen_page = await inspect(link)
                    if match:
                        chosen_candidate = link
                        break

        diagnostics_json = json.dumps(row["_attempt_diagnostics"], separators=(",", ":"))
        if match is None:
            return row, None, "not_found", "low", f"no ATS fingerprint; diagnostics={diagnostics_json}"
        row["careers_url"] = chosen_page["url"]
        evidence = (
            f"discovered_careers_url={row['careers_url']} via {chosen_candidate}; "
            f"{match.evidence}; diagnostics={diagnostics_json}"
        )
        if not match.supported:
            return row, match, "unsupported", "high", evidence
        async with semaphore:
            verified = await verify_match(client, match, poller_fetcher)
        if not verified:
            return row, match, "error", "low", f"verification failed: {evidence}"
        return row, match, "detected", "high", evidence
    except Exception as exc:
        diagnostics_json = json.dumps(row.get("_attempt_diagnostics", []), separators=(",", ":"))
        return row, None, "error", "low", f"{type(exc).__name__}: {exc}; diagnostics={diagnostics_json}"


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
    protected = status != "detected"
    db.execute(text("""
        UPDATE company_registry SET detected_ats=:ats, detected_slug=:slug,
            workday_host=:host, workday_tenant=:tenant, workday_site=:site,
            detection_status=:status, detection_confidence=:confidence,
            detection_evidence=:evidence, board_id=:board_id, careers_url=:careers_url,
            adapter_config=CAST(:adapter_config AS jsonb),
            last_detected_at=now(), updated_at=now() WHERE id=:id
              AND (NOT :protected OR detection_status <> 'detected')
    """), {
        "ats": match.ats if match else None, "slug": match.slug if match else None,
        "host": match.workday_host if match else None,
        "tenant": match.workday_tenant if match else None,
        "site": match.workday_site if match else None,
        "status": status, "confidence": confidence, "evidence": evidence,
        "board_id": board_id, "careers_url": row.get("careers_url"), "id": row["id"],
        "adapter_config": json.dumps(match.endpoint_params if match else {}),
        "protected": protected,
    })


def selection_where(retry_errors: bool) -> str:
    if retry_errors:
        return "detection_status = 'error'"
    return "(detection_status IN ('pending','error') OR last_detected_at < now()-interval '30 days')"


def write_review_csv(path: Path, results) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow((
            "company_name", "careers_url", "status", "detected_ats",
            "elapsed_seconds", "evidence", "attempt_diagnostics",
        ))
        for row, match, status, _confidence, evidence in results:
            if status in {"not_found", "unsupported", "error"}:
                writer.writerow((
                    row["company_name"], row.get("careers_url"), status,
                    match.ats if match else "", row.get("elapsed_seconds", ""), evidence,
                    json.dumps(row.get("_attempt_diagnostics", []), separators=(",", ":")),
                ))


async def run(args):
    db = SessionLocal()
    browser = None
    playwright_cm = None
    poller_fetcher = None
    try:
        where = "TRUE" if args.companies else selection_where(args.retry_errors)
        rows = [dict(row) for row in db.execute(text(f"""
            SELECT id, company_name, domain, careers_url, priority FROM company_registry
            WHERE {where}
            ORDER BY priority, company_name LIMIT :limit
        """), {"limit": args.limit}).mappings().all()]
        known_boards = [dict(row) for row in db.execute(text(KNOWN_BOARDS_SQL)).mappings().all()]
        if args.companies:
            wanted = {name.strip().casefold() for name in args.companies.split(",") if name.strip()}
            rows = [row for row in rows if row["company_name"].casefold() in wanted]
        total = len(rows)
        semaphore = asyncio.Semaphore(args.concurrency)
        worker_semaphore = asyncio.Semaphore(args.concurrency)
        domain_semaphores = {}
        started = time.monotonic()
        tally = {key: 0 for key in ("detected", "unsupported", "not_found", "error")}

        async def loader_for(browser):
            context = await browser.new_context(
                user_agent=BROWSER_USER_AGENT, viewport={"width": 1440, "height": 1000}, locale="en-US"
            )
            page = await context.new_page()
            captured = []
            page.on("request", lambda request: captured.append(request.url))
            async def load(url):
                captured.clear()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1000)
                return {"url": page.url, "html": await page.content(), "network_urls": list(captured),
                        "status_code": response.status if response else None}
            async def close():
                await context.close()
            return load, close

        if args.playwright:
            from playwright.async_api import async_playwright
            playwright_cm = async_playwright()
            pw = await playwright_cm.start()
            browser = await pw.chromium.launch(headless=True)
        poller_fetcher = AsyncBoardFetcher(concurrency=args.concurrency, user_agent=BROWSER_USER_AGENT)

        async def one(index, row):
            async with worker_semaphore:
                company_started = time.monotonic()
                load = playwright_page
                close = None
                if browser:
                    load, close = await loader_for(browser)
                try:
                    result = await asyncio.wait_for(
                        detect_one(client, semaphore, domain_semaphores, row, args.playwright,
                                   playwright_loader=load, known_boards=known_boards,
                                   poller_fetcher=poller_fetcher),
                        timeout=args.timeout,
                    )
                except asyncio.TimeoutError:
                    partial = row.get("_partial_match")
                    result = (row, partial, "error", "low", f"TimeoutError: exceeded {args.timeout}s; partial_diagnostics={len(row.get('_attempt_diagnostics', []))}")
                except Exception as exc:
                    result = (row, None, "error", "low", f"{type(exc).__name__}: {exc}")
                finally:
                    if close:
                        await close()
            row_result, match, status, _confidence, _evidence = result
            tally[status] = tally.get(status, 0) + 1
            elapsed = time.monotonic() - company_started
            row_result["elapsed_seconds"] = round(elapsed, 3)
            ats = match.ats if match else "none"
            print(f"[{index}/{total}] {row['company_name']} -> {status} ({ats}) in {elapsed:.1f}s", flush=True)
            if index % 25 == 0:
                rate = elapsed / index if index else 0
                remaining = max(0, rate * (total - index))
                print(f"tally detected={tally['detected']} unsupported={tally['unsupported']} "
                      f"not_found={tally['not_found']} error={tally['error']} elapsed={elapsed:.1f}s "
                      f"eta={remaining:.1f}s", flush=True)
            if not args.dry_run:
                def persist():
                    session = SessionLocal()
                    try:
                        persist_result(session, *result)
                        session.commit()
                    except Exception:
                        session.rollback()
                        raise
                    finally:
                        session.close()
                try:
                    await asyncio.to_thread(persist)
                except Exception as exc:
                    # A database failure for one company must not cancel the run.
                    result = (row_result, match, "error", "low", f"{type(exc).__name__}: {exc}")
            return result

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=20, verify=True, http2=True,
            headers=DISCOVERY_HEADERS,
        ) as client:
            results = await asyncio.gather(*(one(index, row) for index, row in enumerate(rows, 1)))
        summary = {}
        for _row, match, status, _confidence, _evidence in results:
            key = (match.ats if match else "none", status)
            summary[key] = summary.get(key, 0) + 1
        for (ats, status), count in sorted(summary.items()):
            print(f"ats={ats} status={status} count={count}")
        review = Path(args.review_csv)
        write_review_csv(review, results)
        print(f"review_csv={review}", flush=True)
    except Exception:
        db.rollback()
        raise
    finally:
        if browser:
            await browser.close()
        if poller_fetcher:
            await poller_fetcher.__aexit__(None, None, None)
        if playwright_cm:
            await playwright_cm.__aexit__(None, None, None)
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000000)
    parser.add_argument("--playwright", action="store_true")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--companies", help="Comma-separated company names")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--review-csv", default=str(ROOT / "reports" / "ats_detection_review.csv"))
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
