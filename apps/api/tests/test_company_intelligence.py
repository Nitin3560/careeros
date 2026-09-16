from datetime import datetime
from types import SimpleNamespace

from app import models
from app.services.company_intelligence import (
    infer_sponsorship_status,
    opportunity_quality_score,
    summarize_company_jobs,
)


def job(title, description="", location="Remote", eligible=True):
    return SimpleNamespace(
        title=title,
        description_text=description,
        location=location,
        eligible=eligible,
        last_verified_at=None,
        last_seen_at=datetime(2026, 9, 15),
        retrieved_at=datetime(2026, 9, 15),
    )


def test_infer_sponsorship_status_treats_explicit_no_as_hard_no():
    text = "We are unable to sponsor employment visas now or in the future. H-1B history preferred."

    assert infer_sponsorship_status(text) == "no"


def test_summarize_company_jobs_counts_search_quality_signals():
    jobs = [
        job(
            "New Grad Software Engineer",
            "Visa sponsorship available for this role.",
            "Chicago, IL",
        ),
        job("Senior Sales Engineer", "Quota role", "Austin, TX", eligible=False),
        job("Robotics Software Engineer", "Build controls systems.", "Chicago, IL"),
    ]

    signals = summarize_company_jobs("example", jobs)

    assert signals.open_job_count == 3
    assert signals.new_grad_job_count == 1
    assert signals.matching_job_count == 2
    assert signals.target_locations == ["Chicago, IL", "Austin, TX"]
    assert signals.explicit_sponsorship_status == "yes"


def test_opportunity_quality_score_combines_independent_signals():
    record = models.CompanyIntelligence(
        company="example",
        matching_job_count=3,
        new_grad_job_count=1,
        h1b_software_lca_1y=4,
        explicit_sponsorship_status="probable",
        warn_severity="green",
    )

    assert opportunity_quality_score(record) == 63
