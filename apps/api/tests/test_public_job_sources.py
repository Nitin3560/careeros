from app.services.job_ingestion import (
    amazon,
    ashby,
    lever,
    linkedin,
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


class FakeAmazonResponse:
    def __init__(self, jobs, hits):
        self._jobs = jobs
        self._hits = hits

    def raise_for_status(self):
        return None

    def json(self):
        return {"hits": self._hits, "jobs": self._jobs}


class FakeLinkedInResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return [
            {
                "jobId": "li-1",
                "title": "Software Engineer, AI Infrastructure",
                "companyName": "ExampleAI",
                "location": "United States",
                "description": "Build model-serving systems.",
                "link": "https://www.linkedin.com/jobs/view/li-1",
                "postedDate": "2026-09-03",
            }
        ]


def amazon_job(job_id, title="Software Development Engineer"):
    return {
        "id_icims": job_id,
        "title": title,
        "normalized_location": "Seattle, Washington, USA",
        "description": "Build distributed services.",
        "basic_qualifications": "Bachelor's degree or equivalent.",
        "preferred_qualifications": "Experience with Python.",
        "url_next_step": f"https://account.amazon.jobs/jobs/{job_id}/apply",
        "posted_date": "May 27, 2026",
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


def test_fetch_amazon_jobs_paginates_and_normalizes_response(monkeypatch):
    requested = []
    pages = {
        0: FakeAmazonResponse([amazon_job("100"), amazon_job("101")], hits=3),
        2: FakeAmazonResponse([amazon_job("102", "SDE I")], hits=3),
    }

    def fake_get(url, params, timeout):
        requested.append({"url": url, "params": params, "timeout": timeout})
        return pages[params["offset"]]

    monkeypatch.setattr(amazon.httpx, "get", fake_get)
    monkeypatch.setattr(amazon, "RESULT_LIMIT", 2)

    jobs = amazon.fetch_amazon_jobs("software-development-engineer")

    assert [call["params"]["offset"] for call in requested] == [0, 2]
    assert requested[0]["url"] == "https://www.amazon.jobs/en/search.json"
    assert requested[0]["params"]["base_query"] == "software development engineer"
    assert requested[0]["params"]["country"] == "USA"
    assert requested[0]["timeout"] == 15.0
    assert len(jobs) == 3
    assert jobs[0]["external_id"] == "amazon_100"
    assert jobs[0]["source"] == "amazon"
    assert jobs[0]["company"] == "amazon"
    assert jobs[0]["location"] == "Seattle, Washington, USA"
    assert "Build distributed services." in jobs[0]["description_text"]
    assert "Bachelor's degree or equivalent." in jobs[0]["description_text"]
    assert jobs[0]["application_url"] == "https://account.amazon.jobs/jobs/100/apply"
    assert jobs[0]["date_posted"].year == 2026


def test_build_linkedin_actor_input_uses_daily_swe_filters():
    payload = linkedin.build_actor_input("backend engineer")

    assert payload["query"] == "backend engineer"
    assert payload["location"] == "United States"
    assert payload["datePosted"] == "past24Hours"
    assert payload["experienceLevel"] == ["entry", "associate", "mid"]
    assert "software development engineer" in payload["titleInclude"]
    assert "sales engineer" in payload["titleExclude"]
    assert payload["maxItems"] == 400


def test_fetch_linkedin_jobs_requires_apify_token(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)

    try:
        linkedin.fetch_linkedin_jobs()
    except RuntimeError as exc:
        assert "APIFY_TOKEN" in str(exc)
    else:
        raise AssertionError("expected APIFY_TOKEN failure")


def test_fetch_linkedin_jobs_normalizes_actor_response(monkeypatch):
    requested = {}
    monkeypatch.setenv("APIFY_TOKEN", "test-token")

    def fake_post(url, params, json, timeout):
        requested["url"] = url
        requested["params"] = params
        requested["json"] = json
        requested["timeout"] = timeout
        return FakeLinkedInResponse()

    monkeypatch.setattr(linkedin.httpx, "post", fake_post)

    jobs = linkedin.fetch_linkedin_jobs("backend-engineer")

    assert requested["url"].endswith("/acts/valig~linkedin-jobs-scraper/run-sync-get-dataset-items")
    assert requested["params"]["token"] == "test-token"
    assert requested["params"]["clean"] == "true"
    assert requested["json"]["query"] == "backend engineer"
    assert requested["timeout"] == 180.0
    assert jobs[0]["external_id"] == "linkedin_li-1"
    assert jobs[0]["source"] == "linkedin"
    assert jobs[0]["company"] == "exampleai"
    assert jobs[0]["title"] == "Software Engineer, AI Infrastructure"
    assert jobs[0]["location"] == "United States"
    assert jobs[0]["description_text"] == "Build model-serving systems."
    assert jobs[0]["application_url"] == "https://www.linkedin.com/jobs/view/li-1"
    assert jobs[0]["date_posted"].year == 2026


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


def test_source_fetchers_include_linkedin():
    assert public_sources.SOURCE_FETCHERS["linkedin"] is linkedin.fetch_linkedin_jobs
