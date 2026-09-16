from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.services.job_ingestion.persist import (
    build_identity_key,
    build_queue_key,
    canonicalize_url,
    clean_job,
    save_jobs,
)


def test_clean_job_removes_nul_from_text_fields():
    job = {
        "external_id": "greenhouse_1",
        "title": "Software\x00 Engineer",
        "description_text": "Build\x00 systems",
        "location": None,
    }

    assert clean_job(job) == {
        "external_id": "greenhouse_1",
        "title": "Software Engineer",
        "description_text": "Build systems",
        "location": None,
    }


def test_canonicalize_url_removes_tracking_params():
    url = "HTTPS://Example.com/jobs/123/?utm_source=li&ref=abc&foo=bar"

    assert canonicalize_url(url) == "https://example.com/jobs/123?foo=bar"


def test_canonicalize_url_keeps_ats_job_id_params():
    url = "https://careers.example.com/jobs?gh_jid=123&utm_source=linkedin"

    assert canonicalize_url(url) == "https://careers.example.com/jobs?gh_jid=123"


def test_build_identity_key_prefers_canonical_url():
    job = {
        "company": "Example AI",
        "title": "Software Engineer",
        "location": "Remote",
        "application_url": "https://jobs.example.com/123?utm_medium=social",
    }

    assert build_identity_key(job) == "url:https://jobs.example.com/123"


def test_build_queue_key_collapses_city_specific_role_titles():
    first = {
        "company": "Speechify",
        "title": "Senior Software Engineer, Core Experiences - Chicago, IL, USA",
    }
    second = {
        "company": "Speechify",
        "title": "Senior Software Engineer, Core Experiences - Dallas, TX, USA",
    }

    assert build_queue_key(first) == build_queue_key(second)
    assert build_queue_key(first) == "queue:speechify|senior software engineer core experiences"


def test_save_jobs_refreshes_existing_job_lifecycle():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Job.__table__.create(engine)

    with Session(engine) as db:
        first = save_jobs(
            db,
            [
                {
                    "external_id": "greenhouse_1",
                    "source": "greenhouse",
                    "company": "example",
                    "title": "Old Title",
                    "location": "Remote",
                    "description_text": "Old description",
                    "application_url": "https://jobs.example.com/1?utm_source=x",
                }
            ],
        )
        second = save_jobs(
            db,
            [
                {
                    "external_id": "greenhouse_1",
                    "source": "greenhouse",
                    "company": "example",
                    "title": "New Title",
                    "location": "Remote",
                    "description_text": "New description",
                    "application_url": "https://jobs.example.com/1?utm_source=y",
                }
            ],
        )

        job = db.query(models.Job).filter_by(external_id="greenhouse_1").one()

    assert first == {"inserted": 1, "refreshed": 0, "skipped": 0}
    assert second == {"inserted": 0, "refreshed": 1, "skipped": 0}
    assert job.title == "New Title"
    assert job.description_text == "New description"
    assert job.canonical_url == "https://jobs.example.com/1"
    assert job.identity_key == "url:https://jobs.example.com/1"
    assert job.queue_key == "queue:example|new title"
    assert job.seen_count == 2
