from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from update_entry_jobs_readme import (  # noqa: E402
    EntryJob,
    extract_entry_experience,
    extract_salary,
    format_time_ago,
    is_eligible_tech_title,
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


def test_eligible_tech_title_keeps_broader_non_senior_tech_roles_for_tier_c():
    assert is_eligible_tech_title("Software Development Engineer, AWS Lambda")
    assert is_eligible_tech_title("AI Engineer")
    assert is_eligible_tech_title("Backend Developer")
    assert is_eligible_tech_title("Software Engineer, Early Career — Immediate Start", "This role is classified as exempt.")


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
    assert not is_eligible_tech_title("Product Design, Entry-Level")
    assert not is_eligible_tech_title("Junior Investment Analyst")
    assert not is_eligible_tech_title("Mechanical Engineer I")
    assert not is_eligible_tech_title("Radiation Effects Engineer I")
    assert not is_eligible_tech_title("GNC Simulation Engineer I")
    assert not is_eligible_tech_title("Software Development Engineer III")
    assert not is_eligible_tech_title("Software Development Engineer, Strategic Defense")
    assert not is_eligible_tech_title("Software and Mobility Asset Supervisor")
    assert not is_eligible_tech_title("Environmental Services & Facilities Technician (FT, Front End Days)")


def test_extract_salary_from_posting_text():
    assert extract_salary("The salary range is $120,000 - $155,000 per year.") == "$120,000 - $155,000"
    assert extract_salary("Compensation: $45/hr") == "$45/hr"
    assert extract_salary("No range shown") == ""


def test_experience_filter_requires_zero_to_two_years_from_posting():
    assert extract_entry_experience("No professional experience required; we will train you.") == "0 years"
    assert extract_entry_experience("Requires 1+ year of professional software development experience.") == "1 year"
    assert extract_entry_experience("You have 1-2 years of relevant engineering experience.") == "1–2 years"
    assert extract_entry_experience("Requires 2 years of software engineering experience.") == "2 years"
    assert extract_entry_experience("Minimum 2 years of software engineering experience.") is None
    assert extract_entry_experience("Requires 2+ years of professional software experience.") is None
    assert extract_entry_experience("At least 2 years of relevant engineering experience.") is None
    assert extract_entry_experience("2 years minimum of professional experience.") is None
    assert extract_entry_experience(
        "Basic Qualifications\n"
        "2+ years of non-internship design or architecture (design patterns, reliability, and scaling) "
        "of new and existing systems experience\n"
        "1+ years of software development engineer or related occupational experience"
    ) is None
    assert extract_entry_experience("Requires 3+ years of professional experience.") is None
    assert extract_entry_experience("Software engineering experience is useful.") is None


def test_found_age_is_human_readable():
    now = datetime(2026, 9, 19, 20, 0, tzinfo=timezone.utc)
    assert format_time_ago(datetime(2026, 9, 19, 19, 59, 30, tzinfo=timezone.utc), now) == "just now"
    assert format_time_ago(datetime(2026, 9, 19, 19, 2, tzinfo=timezone.utc), now) == "58 min ago"
    assert format_time_ago(datetime(2026, 9, 19, 16, 0, tzinfo=timezone.utc), now) == "4 hours ago"
    assert format_time_ago(datetime(2026, 9, 17, 20, 0, tzinfo=timezone.utc), now) == "2 days ago"


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
        experience="0–2 years",
        dedupe_key=f"queue:{company}:{title}",
    )


def test_tier_for_job_uses_company_size_not_title_or_pay():
    assert tier_for_job(make_job("amazon", "Software Engineer")) == "Tier 1"
    assert tier_for_job(make_job("samsara", "Software Engineer")) == "Tier 2"
    assert tier_for_job(make_job("smallco", "Software Engineer")) == "Tier 3"


def test_render_and_update_marked_readme_with_three_tiers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Profile\n\nold\n")
    jobs = [
        make_job("stripe", "Software Engineer, Early Career", "$120,000 - $155,000"),
        make_job("samsara", "Software Engineer I"),
        make_job("smallco", "Software Development Engineer, AWS Lambda"),
    ]

    block = render_markdown(
        jobs,
        since_hours=168,
        now=datetime(2026, 9, 19, 20, 0, tzinfo=timezone.utc),
    )
    assert update_readme(readme, block)
    content = readme.read_text()

    assert "<!-- ENTRY_JOBS:START -->" in content
    assert "Speed: CareerOS refreshes every hour" in content
    assert "Quick links: [Tier 1](#tier-1)" in content
    assert "### Tier 1" in content
    assert "### Tier 2" in content
    assert "### Tier 3" in content
    assert "| Company | Role | Experience | Posted | Found | Salary | Apply |" in content
    assert "1 hour ago" in content
    assert "$120,000 - $155,000" in content
    assert "[Apply](https://example.com/stripe)" in content
