from app.services.job_ingestion.persist import clean_job


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
