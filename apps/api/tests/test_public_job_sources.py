from app.services.job_ingestion import (
    ashby,
    lever,
    public_sources,
    smartrecruiters,
    workable,
)


class FakeLeverResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return [
            {
                "id": "abc",
                "text": "Systems Engineer",
                "categories": {"location": "Austin, TX"},
                "descriptionPlain": "Build systems",
                "hostedUrl": "https://jobs.example.com/abc",
                "createdAt": 1780000000000,
            }
        ]


class FakeAshbyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "jobs": [
                {
                    "id": "job-1",
                    "title": "Robotics Engineer",
                    "location": {"name": "Remote"},
                    "descriptionHtml": "<p>Build robots</p>",
                    "jobUrl": "https://jobs.example.com/job-1",
                    "publishedAt": "2026-08-14T12:30:00Z",
                }
            ]
        }


class FakeSmartRecruitersResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "totalFound": 1,
            "content": [
                {
                    "id": "job-2",
                    "name": "Platform Engineer",
                    "location": {"city": "Austin", "region": "TX", "country": "USA"},
                    "applyUrl": "https://jobs.example.com/job-2",
                    "releasedDate": "2026-08-14T12:30:00Z",
                }
            ],
        }


class FakeWorkableResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "jobs": [
                {
                    "shortcode": "ABC123",
                    "title": "Backend Engineer",
                    "location": {"city": "Remote", "country": "USA"},
                    "description": "Build APIs",
                    "url": "https://apply.workable.com/example/j/ABC123/",
                    "published": "2026-08-14T12:30:00Z",
                }
            ]
        }


def test_fetch_lever_jobs_normalizes_public_response(monkeypatch):
    requested = {}

    def fake_get(url, timeout):
        requested["url"] = url
        requested["timeout"] = timeout
        return FakeLeverResponse()

    monkeypatch.setattr(lever.httpx, "get", fake_get)

    jobs = lever.fetch_lever_jobs("amd")

    assert requested["url"] == "https://api.lever.co/v0/postings/amd?mode=json"
    assert requested["timeout"] == 10.0
    assert jobs[0]["external_id"] == "lever_abc"
    assert jobs[0]["source"] == "lever"
    assert jobs[0]["company"] == "amd"
    assert jobs[0]["title"] == "Systems Engineer"
    assert jobs[0]["location"] == "Austin, TX"


def test_fetch_ashby_jobs_normalizes_public_response(monkeypatch):
    requested = {}

    def fake_get(url, timeout):
        requested["url"] = url
        requested["timeout"] = timeout
        return FakeAshbyResponse()

    monkeypatch.setattr(ashby.httpx, "get", fake_get)

    jobs = ashby.fetch_ashby_jobs("example")

    assert requested["url"] == "https://api.ashbyhq.com/posting-api/job-board/example"
    assert requested["timeout"] == 10.0
    assert jobs[0]["external_id"] == "ashby_job-1"
    assert jobs[0]["source"] == "ashby"
    assert jobs[0]["company"] == "example"
    assert jobs[0]["description_text"] == "<p>Build robots</p>"


def test_fetch_smartrecruiters_jobs_normalizes_public_response(monkeypatch):
    requested = {}

    def fake_get(url, params, timeout):
        requested["url"] = url
        requested["params"] = params
        requested["timeout"] = timeout
        return FakeSmartRecruitersResponse()

    monkeypatch.setattr(smartrecruiters.httpx, "get", fake_get)

    jobs = smartrecruiters.fetch_smartrecruiters_jobs("example")

    assert requested["url"] == "https://api.smartrecruiters.com/v1/companies/example/postings"
    assert requested["params"] == {"offset": 0, "limit": 100}
    assert requested["timeout"] == 10.0
    assert jobs[0]["external_id"] == "smartrecruiters_job-2"
    assert jobs[0]["source"] == "smartrecruiters"
    assert jobs[0]["company"] == "example"
    assert jobs[0]["title"] == "Platform Engineer"
    assert jobs[0]["location"] == "Austin, TX, USA"


def test_fetch_workable_jobs_normalizes_public_response(monkeypatch):
    requested = {}

    def fake_get(url, timeout):
        requested["url"] = url
        requested["timeout"] = timeout
        return FakeWorkableResponse()

    monkeypatch.setattr(workable.httpx, "get", fake_get)

    jobs = workable.fetch_workable_jobs("example")

    assert requested["url"] == "https://apply.workable.com/api/v1/widget/accounts/example"
    assert requested["timeout"] == 10.0
    assert jobs[0]["external_id"] == "workable_ABC123"
    assert jobs[0]["source"] == "workable"
    assert jobs[0]["company"] == "example"
    assert jobs[0]["title"] == "Backend Engineer"
    assert jobs[0]["description_text"] == "Build APIs"


def test_discover_public_source_uses_known_source(monkeypatch):
    monkeypatch.setitem(
        public_sources.KNOWN_PUBLIC_SOURCES,
        "example-co",
        [("lever", "example")],
    )
    monkeypatch.setitem(
        public_sources.SOURCE_FETCHERS,
        "lever",
        lambda slug: [{"external_id": f"lever_{slug}"}],
    )

    source = public_sources.discover_public_source("Example Co")

    assert source.source == "lever"
    assert source.slug == "example"
    assert source.fetch(source.slug)[0]["external_id"] == "lever_example"


def test_default_candidates_include_added_sources_and_slug_variants():
    candidates = public_sources.default_candidates("dell-technologies")

    assert ("greenhouse", "delltechnologies") in candidates
    assert ("smartrecruiters", "delltechnologies") in candidates
    assert ("workable", "delltechnologies") in candidates
    assert ("greenhouse", "dell") in candidates
    assert ("workable", "dell") in candidates
