import asyncio
from pathlib import Path
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.ingestion.registry_detection import find_ats, verify_match
from scripts.detect_ats import persist_result


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


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _RegistryDB:
    def __init__(self):
        self.board_id = None
        self.board_inserts = 0

    def execute(self, statement, params):
        sql = str(statement)
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
    persist_result(db, row, match, "detected", "high", match.evidence)
    persist_result(db, row, match, "detected", "high", match.evidence)
    assert db.board_inserts == 1
