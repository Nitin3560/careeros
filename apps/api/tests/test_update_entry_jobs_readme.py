from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from update_entry_jobs_readme import (  # noqa: E402
    EntryJob,
    extract_salary,
    is_entry_full_time_title,
    is_us_location,
    render_markdown,
    tier_for_job,
    update_readme,
)


def test_entry_title_filter_keeps_full_time_entry_signals():
    assert is_entry_full_time_title("Software Engineer, New Grad")
    assert is_entry_full_time_title("Software Development Engineer I")
    assert is_entry_full_time_title("Engineer I, Backend")
    assert is_entry_full_time_title("Member of Technical Staff")
    assert is_entry_full_time_title("MTS, Platform")


def test_location_filter_requires_us_signal_first():
    assert is_us_location("San Francisco, Seattle, New York")
    assert is_us_location("Long Beach, California, United States")
    assert is_us_location("Redlands, CA")
    assert is_us_location("Remote - United States")
    assert not is_us_location("London, England, United Kingdom")
    assert not is_us_location("Toronto")
    assert not is_us_location("Ho Chi Minh City, Vietnam")
    assert not is_us_location("Prague, Czech Republic")


def test_entry_title_filter_excludes_intern_senior_and_non_engineering_noise():
    assert not is_entry_full_time_title("Software Development Engineer Intern")
    assert not is_entry_full_time_title("Senior Software Engineer")
    assert not is_entry_full_time_title("Staff Software Engineer")
    assert not is_entry_full_time_title("Entry Level Tech Sales - UK&I Market")
    assert not is_entry_full_time_title("Product Design, Entry-Level")
    assert not is_entry_full_time_title("Junior Investment Analyst")
    assert not is_entry_full_time_title("Mechanical Engineer I")
    assert not is_entry_full_time_title("Radiation Effects Engineer I")
    assert not is_entry_full_time_title("GNC Simulation Engineer I")


def test_extract_salary_from_posting_text():
    assert extract_salary("The salary range is $120,000 - $155,000 per year.") == "$120,000 - $155,000"
    assert extract_salary("Compensation: $45/hr") == "$45/hr"
    assert extract_salary("No range shown") == ""


def make_job(company, title, salary="", location="Remote - US"):
    return EntryJob(
        company=company,
        title=title,
        location=location,
        date_posted=datetime(2026, 9, 19, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 9, 19, 19, tzinfo=timezone.utc),
        application_url=f"https://example.com/{company}",
        source="greenhouse",
        salary=salary,
    )


def test_tier_for_job_splits_a_b_c():
    assert tier_for_job(make_job("stripe", "Software Engineer, Early Career")) == "Tier A"
    assert tier_for_job(make_job("samsara", "Software Engineer I")) == "Tier B"
    assert tier_for_job(make_job("smallco", "Member of Technical Staff")) == "Tier C"


def test_render_and_update_marked_readme_with_three_tiers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Profile\n\nold\n")
    jobs = [
        make_job("stripe", "Software Engineer, Early Career", "$120,000 - $155,000"),
        make_job("samsara", "Software Engineer I"),
        make_job("smallco", "Member of Technical Staff"),
    ]

    block = render_markdown(jobs, since_hours=168)
    assert update_readme(readme, block)
    content = readme.read_text()

    assert "<!-- ENTRY_JOBS:START -->" in content
    assert "Quick links: [Tier A](#tier-a)" in content
    assert "### Tier A" in content
    assert "### Tier B" in content
    assert "### Tier C" in content
    assert "| Company | Role | Posted | Found | Salary | Apply |" in content
    assert "2026-09-19 19:00 UTC" in content
    assert "$120,000 - $155,000" in content
    assert "[Apply](https://example.com/stripe)" in content
