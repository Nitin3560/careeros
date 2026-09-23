import asyncio
import csv
import json
from pathlib import Path
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.ingestion.registry_detection import find_ats, verify_match
from scripts.detect_ats import (
    careers_candidates,
    detect_one,
    persist_result,
    probe_url,
    selection_where,
    write_review_csv,
)


@pytest.mark.parametrize(("markup", "ats", "slug"), [
    ('<a href="https://boards.greenhouse.io/acme/jobs/1">Jobs</a>', "greenhouse", "acme"),
    ('<script src="https://boards.greenhouse.io/embed/job_board?for=embedded"></script>', "greenhouse", "embedded"),
    ('<script src="https://api.lever.co/v0/postings/rocket"></script>', "lever", "rocket"),
    ('<iframe src="https://jobs.ashbyhq.com/vector"></iframe>', "ashby", "vector"),
])
def test_supported_static_fingerprints(markup, ats, slug):
    match = find_ats([], "https://example.com/careers", markup)
    assert (match.ats, match.slug, match.supported) == (ats, slug, True)


def test_redirect_chain_and_embedded_board_are_scanned():
    match = find_ats(
        ["https://example.com/jobs", "https://boards.greenhouse.io/redirected"],
        "https://example.com/final", '<a href="https://smartrecruiters.com/acme">Other</a>',
    )
    assert (match.ats, match.slug) == ("greenhouse", "redirected")


def test_workday_locale_url_captures_host_tenant_and_site():
    match = find_ats([], "https://acme.wd5.myworkdayjobs.com/en-US/External", "")
    assert match.ats == "workday"
    assert match.workday_host == "acme.wd5.myworkdayjobs.com"
    assert match.workday_tenant == "acme"
    assert match.workday_site == "External"
    assert match.slug == "acme.wd5.myworkdayjobs.com|acme|External"


@pytest.mark.parametrize("url,ats,slug", [
    ("https://jobs.smartrecruiters.com/Acme", "smartrecruiters", "Acme"),
    ("https://apply.workable.com/acme/", "workable", "acme"),
    ("https://careers.acme.com/api/phenom/jobapi/searchjobs", "phenom", "careers.acme.com|careers"),
    ("https://acme.eightfold.ai/careers", "eightfold", "acme.eightfold.ai|acme"),
    ("https://acme.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/External?siteNumber=External", "oracle", "acme.fa.us2.oraclecloud.com|External"),
    ("https://careers-acme.icims.com/jobs/search", "icims", "careers-acme.icims.com"),
])
def test_supported_adapters_capture_board_endpoint_parameters(url, ats, slug):
    match = find_ats([], url, "")
    assert match.ats == ats and match.slug == slug and match.supported
    if ats in {"phenom", "eightfold", "oracle", "icims"}:
        assert match.endpoint_params["host"] in slug
        assert match.endpoint_params["endpoint"].startswith("https://")
    else:
        assert match.endpoint_params["company_slug"] == slug


def test_embedded_supported_board_beats_generic_unsupported_link():
    markup = '<a href="https://smartrecruiters.com/acme">old</a><iframe src="https://jobs.ashbyhq.com/acme"></iframe>'
    assert find_ats([], "https://example.com", markup).ats == "ashby"


def test_verification_failure_is_false_and_cannot_be_accepted():
    async def scenario():
        def handler(request):
            return httpx.Response(200, request=request, json={"unexpected": []})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            match = find_ats([], "https://jobs.ashbyhq.com/acme", "")
            assert await verify_match(client, match) is False
    asyncio.run(scenario())


def test_verification_ignores_html_json_decode_error():
    async def scenario():
        def handler(request):
            return httpx.Response(200, request=request, text="<html>not json</html>")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            match = find_ats([], "https://jobs.ashbyhq.com/acme", "")
            assert await verify_match(client, match) is False
    asyncio.run(scenario())


def test_template_urls_are_not_fingerprinted():
    markup = '<a href="https://aexp.eightfold.ai/careers?query=${Title}`">roles</a>'
    assert find_ats([], "https://example.com/careers", markup) is None


def test_conflicting_fingerprints_are_preserved_in_evidence():
    markup = (
        '<script src="https://aexp.eightfold.ai/careers"></script>'
        '<script src="https://aexp.fa.us2.oraclecloud.com/hcmUI/CandidateExperience?siteNumber=External"></script>'
    )
    match = find_ats([], "https://example.com/careers", markup)
    assert "all_fingerprints" in match.evidence
    assert "eightfold" in match.evidence and "oracle" in match.evidence


@pytest.mark.parametrize("url,payload", [
    ("https://careers.acme.com/api/phenom/jobapi/searchjobs", {"data": {"jobs": []}}),
    ("https://acme.eightfold.ai/careers", {"positions": []}),
    ("https://acme.oraclecloud.com/hcmUI/CandidateExperience?siteNumber=External", {"items": []}),
    ("https://careers-acme.icims.com/jobs/search", {"jobs": []}),
])
def test_tenant_adapter_fingerprint_is_verified_with_list_shape(url, payload):
    async def scenario():
        def handler(request):
            return httpx.Response(200, request=request, json=payload)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assert await verify_match(client, find_ats([], url, "")) is True
    asyncio.run(scenario())


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _RegistryDB:
    def __init__(self):
        self.board_id = None
        self.board_inserts = 0
        self.statements = []

    def execute(self, statement, params):
        sql = str(statement)
        self.statements.append((sql, params))
        if "SELECT id FROM ats_boards" in sql:
            return _ScalarResult(self.board_id)
        if "INSERT INTO ats_boards" in sql:
            self.board_id = params["id"]
            self.board_inserts += 1
        return _ScalarResult(None)


def test_detection_persistence_is_idempotent_and_failure_inserts_nothing():
    db = _RegistryDB()
    row = {"id": uuid.uuid4(), "company_name": "Acme", "priority": 2}
    match = find_ats([], "https://jobs.ashbyhq.com/acme", "")
    persist_result(db, row, match, "error", "low", "verification failed")
    assert db.board_inserts == 0
    registry_update = next(item for item in db.statements if "UPDATE company_registry" in item[0])
    assert "detection_status <> 'detected'" in registry_update[0]
    assert registry_update[1]["protected"] is True
    persist_result(db, row, match, "detected", "high", match.evidence)
    persist_result(db, row, match, "detected", "high", match.evidence)
    assert db.board_inserts == 1


def test_careers_candidates_follow_required_order():
    candidates = careers_candidates("example.com")
    assert candidates[:7] == [
        "https://example.com/careers",
        "https://example.com/jobs",
        "https://careers.example.com",
        "https://jobs.example.com",
        "https://www.example.com/careers",
        "https://www.example.com/jobs",
        "https://example.com",
    ]
    assert candidates[7:] == [
        "https://example.com/about/careers",
        "https://example.com/company/careers",
        "https://example.com/company/jobs",
        "https://example.com/join",
        "https://example.com/join-us",
        "https://example.com/work-with-us",
        "https://example.com/careers/jobs",
        "https://example.com/en/careers",
        "https://example.com/careers/open-positions",
    ]


def test_blank_careers_url_is_discovered_persisted_and_verified():
    async def scenario():
        def handler(request):
            url = str(request.url)
            if "api.ashbyhq.com" in url:
                return httpx.Response(200, request=request, json={"jobs": []})
            if url == "https://careers.example.com":
                return httpx.Response(
                    200, request=request,
                    text='<iframe src="https://jobs.ashbyhq.com/example"></iframe>',
                )
            return httpx.Response(404, request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            row = {
                "id": uuid.uuid4(), "company_name": "Example", "domain": "example.com",
                "careers_url": None, "priority": 2,
            }
            result = await detect_one(client, asyncio.Semaphore(8), {}, row)
        returned_row, match, status, confidence, evidence = result
        assert (match.ats, status, confidence) == ("ashby", "detected", "high")
        assert returned_row["careers_url"] == "https://careers.example.com"
        assert [item["url"] for item in returned_row["_attempt_diagnostics"]] == careers_candidates("example.com")[:3]
        assert "discovered_careers_url=https://careers.example.com" in evidence

    asyncio.run(scenario())


def test_discovery_limits_concurrent_requests_per_domain_to_three():
    async def scenario():
        active = 0
        maximum = 0

        async def handler(request):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return httpx.Response(200, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            domain_semaphores = {}
            await asyncio.gather(*(
                probe_url(
                    client, asyncio.Semaphore(20), domain_semaphores,
                    "example.com", "https://example.com/careers",
                )
                for _ in range(8)
            ))
        assert maximum == 3

    asyncio.run(scenario())


def test_not_found_discovery_retains_every_attempted_url():
    async def scenario():
        def handler(request):
            return httpx.Response(404, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            row = {
                "id": uuid.uuid4(), "company_name": "Missing", "domain": "missing.example",
                "careers_url": None, "priority": 2,
            }
            returned_row, _match, status, _confidence, evidence = await detect_one(
                client, asyncio.Semaphore(8), {}, row
            )
        assert status == "not_found"
        attempted = [item["url"] for item in returned_row["_attempt_diagnostics"] if not item["playwright"]]
        assert attempted == careers_candidates("missing.example") + ["https://missing.example/sitemap.xml"]
        assert "final_status_code" in evidence

    asyncio.run(scenario())


def test_403_plain_http_then_playwright_success_is_detected():
    async def scenario():
        def handler(request):
            if "boards-api.greenhouse.io" in str(request.url):
                return httpx.Response(200, request=request, json={"jobs": []})
            return httpx.Response(403, request=request, text="blocked")

        async def browser(url):
            return {
                "url": url, "status_code": 200,
                "html": '<iframe src="https://boards.greenhouse.io/acme"></iframe>',
                "network_urls": [],
            }

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            row = {"id": uuid.uuid4(), "company_name": "Acme", "domain": "acme.com", "careers_url": None, "priority": 1}
            return await detect_one(client, asyncio.Semaphore(8), {}, row, playwright_loader=browser)

    row, match, status, _confidence, evidence = asyncio.run(scenario())
    assert (match.ats, status) == ("greenhouse", "detected")
    assert row["_attempt_diagnostics"][0]["final_status_code"] == 403
    assert row["_attempt_diagnostics"][1]["playwright"] is True
    assert "diagnostics=" in evidence


def test_homepage_link_discovery_finds_greenhouse_board():
    async def scenario():
        def handler(request):
            url = str(request.url)
            if "boards-api.greenhouse.io" in url:
                return httpx.Response(200, request=request, json={"jobs": []})
            if url == "https://acme.com":
                return httpx.Response(200, request=request, text='<a href="/open-roles">Work with us</a>')
            if url == "https://acme.com/open-roles":
                return httpx.Response(200, request=request, text='<iframe src="https://boards.greenhouse.io/acme"></iframe>')
            return httpx.Response(404, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            row = {"id": uuid.uuid4(), "company_name": "Acme", "domain": "acme.com", "careers_url": None, "priority": 1}
            return await detect_one(client, asyncio.Semaphore(8), {}, row)
    _row, match, status, _confidence, _evidence = asyncio.run(scenario())
    assert (match.ats, status) == ("greenhouse", "detected")


def test_homepage_press_link_is_not_followed():
    async def scenario():
        def handler(request):
            if str(request.url) == "https://acme.com":
                return httpx.Response(200, request=request, text='<a href="/press/jobs-platform">Engineer</a>')
            return httpx.Response(404, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            row = {"id": uuid.uuid4(), "company_name": "Acme", "domain": "acme.com", "careers_url": None, "priority": 1}
            return await detect_one(client, asyncio.Semaphore(8), {}, row)
    _row, match, status, _confidence, _evidence = asyncio.run(scenario())
    assert match is None and status == "not_found"


def test_sitemap_fallback_finds_greenhouse_board():
    async def scenario():
        def handler(request):
            url = str(request.url)
            if "boards-api.greenhouse.io" in url:
                return httpx.Response(200, request=request, json={"jobs": []})
            if url == "https://acme.com/sitemap.xml":
                return httpx.Response(200, request=request, text="<urlset><url><loc>https://acme.com/teams/careers-list</loc></url></urlset>")
            if url == "https://acme.com/teams/careers-list":
                return httpx.Response(200, request=request, text='<a href="https://boards.greenhouse.io/acme">Jobs</a>')
            return httpx.Response(404, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            row = {"id": uuid.uuid4(), "company_name": "Acme", "domain": "acme.com", "careers_url": None, "priority": 1}
            return await detect_one(client, asyncio.Semaphore(8), {}, row)
    _row, match, status, _confidence, _evidence = asyncio.run(scenario())
    assert (match.ats, status) == ("greenhouse", "detected")


def test_review_csv_includes_error_diagnostics_and_retry_selects_only_errors(tmp_path):
    row = {
        "company_name": "Blocked", "careers_url": "https://blocked.test/careers",
        "_attempt_diagnostics": [{
            "url": "https://blocked.test/careers", "final_status_code": 503,
            "redirect_chain": ["https://blocked.test/careers"],
            "exception_type": None, "response_size": 7, "playwright": False,
        }],
    }
    output = tmp_path / "review.csv"
    write_review_csv(output, [(row, None, "error", "low", "blocked")])
    record = next(csv.DictReader(output.open()))
    assert record["status"] == "error"
    assert json.loads(record["attempt_diagnostics"])[0]["final_status_code"] == 503
    assert selection_where(True) == "detection_status = 'error'"
    assert "pending" in selection_where(False)
