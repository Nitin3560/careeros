from dataclasses import replace
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
    collapse_duplicate_locations,
    is_eligible_tech_title,
    has_required_experience_evidence,
    has_explicit_non_us_location,
    is_entry_full_time_title,
    is_us_location,
    markdown_apply_link,
    render_tier_table,
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
    assert has_explicit_non_us_location("Seattle, WA; Amsterdam")
    assert not has_explicit_non_us_location("Boston, MA; Portland, ME")
    assert has_explicit_non_us_location("Boston, MA; London, UK")


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
    assert "| Company | Role | Location | Experience | Posted | Found | Salary | Apply |" in content
    assert "1 hour ago" in content
    assert "$120,000 - $155,000" in content
    assert "[Apply](https://example.com/stripe)" in content


def test_duplicate_identity_collapses_locations_and_preserves_markers():
    first = replace(make_job("Example Inc", "Software Engineer I"), dedupe_key="same-req", locations=("Austin, TX",), is_new=True)
    second = replace(make_job("Example Inc", "Software Engineer I"), dedupe_key="same-req", locations=("Seattle, WA",), is_aggregator=True)
    third = replace(make_job("Other Co", "Software Engineer I"), dedupe_key="same-req")  # collision across employers must not merge
    collapsed = collapse_duplicate_locations([first, second, third])
    assert len(collapsed) == 2
    merged = next(job for job in collapsed if job.company == "Example Inc")
    assert merged.locations == ("Austin, TX", "Seattle, WA")
    assert merged.is_new and merged.is_aggregator


def test_experience_parser_ignores_preferred_and_rejects_any_required_over_two():
    assert extract_entry_experience("## Basic Qualifications\n1+ year of relevant experience\n## Preferred\n5+ years preferred") == "1 year"
    assert extract_entry_experience("## Requirements\n1+ year experience\n3 years of professional experience") is None
    assert extract_entry_experience("## Preferred Qualifications\n3+ years experience") is None
    assert extract_entry_experience("## Requirements\nAt least three years of related experience") is None
    assert extract_entry_experience("## Requirements\nTwo years of professional experience") == "2 years"
    assert has_required_experience_evidence("## Requirements\nThree years experience")
    assert not has_required_experience_evidence("## Preferred Qualifications\nFive years preferred")


def test_duplicate_collapse_does_not_merge_unkeyed_distinct_postings():
    first = replace(make_job("Example Inc", "Software Engineer I"), dedupe_key=None,
                    application_url="https://example.com/jobs/1")
    second = replace(make_job("Example Inc", "Software Engineer I"), dedupe_key=None,
                     application_url="https://example.com/jobs/2")
    assert len(collapse_duplicate_locations([first, second])) == 2


def test_render_marks_unknown_new_and_aggregator_and_groups_by_posted_day():
    job = replace(make_job("Example <Co>", "Software Engineer | Platform"), location=None,
                  locations=(), location_class="unknown", is_new=True, is_aggregator=True)
    rendered = "\n".join(render_tier_table([job], datetime(2026, 9, 19, 20, tzinfo=timezone.utc)))
    assert "#### 2026-09-19" in rendered
    assert "⚠ Unknown location" in rendered
    assert "Second-hand" in rendered
    assert "**NEW**" in rendered
    assert "&lt;Co&gt;" in rendered and "<Co>" not in rendered
    assert "Software Engineer \\| Platform" in rendered


def test_apply_link_rejects_non_web_schemes_and_encodes_markdown_delimiters():
    assert markdown_apply_link("javascript:alert(1)") == ""
    assert markdown_apply_link("https://user:pass@example.com/job") == ""
    assert markdown_apply_link("https://example.com/job (new)") == "[Apply](https://example.com/job%20%28new%29)"
    assert markdown_apply_link("https://exa|mple.com/job") == ""
    assert "&lt;script&gt;" in "\n".join(render_tier_table([replace(make_job("x", "<script>alert(1)</script>"), location_class="us")]))


def test_update_readme_refuses_damaged_or_duplicated_markers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("start <!-- ENTRY_JOBS:START --> only")
    import pytest
    with pytest.raises(ValueError, match="markers"):
        update_readme(readme, "new block")

    readme.write_text("<!-- ENTRY_JOBS:START --> old <!-- ENTRY_JOBS:END -->\n<!-- ENTRY_JOBS:START --> x <!-- ENTRY_JOBS:END -->\n")
    with pytest.raises(ValueError, match="markers"):
        update_readme(readme, "new block")
