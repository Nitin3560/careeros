import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from render_entry_jobs_page import _qualifies_for_page, experience_bucket, is_early_career_job, render_page, split_row  # noqa: E402
from update_entry_jobs_readme import display_company, has_us_url_signal, is_us_location  # noqa: E402


def test_marked_feed_renders_a_mobile_friendly_page_with_all_job_fields():
    readme = """# Example
<!-- ENTRY_JOBS:START -->
## New Grad & Entry-Level Engineering Roles
Auto-updated hourly. Last run: **2026-09-28 12:00 UTC**.
Showing U.S. software and AI postings found in the last **7 days**.
Quick links: [Tier 1](#tier-1) · [Tier 2](#tier-2) · [Tier 3](#tier-3)
### Tier 1
Large public companies.
| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Example Co | Software Engineer I | Seattle, WA | 1 year | 2026-09-27 | 2 hours ago | $100k-$140k | [Apply](https://jobs.example/1) |
### Tier 2
Established mid-sized companies.
No matching roles in this tier right now.
### Tier 3
Startups.
| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Tiny Inc | Junior Backend Engineer | Boston, MA | 0 years | 2026-09-28 | 20 min ago |  | [Apply](https://jobs.example/2) |
<!-- ENTRY_JOBS:END -->
"""
    html = render_page(readme)

    assert "CareerOS Recent U.S. Tech Jobs" in html
    assert "Last run: <strong>2026-09-28 12:00 UTC</strong>" in html
    assert "Seattle, WA" in html
    assert "Experience" in html and "$100k-$140k" in html
    assert "2 hours ago" in html and "2026-09-27" in html
    assert 'href="https://jobs.example/1"' in html
    assert "Tier 1" in html and "Tier 2" in html and "Tier 3" in html
    assert "@media(max-width:600px)" in html
    assert "stylesheet" not in html


def test_renderer_escapes_job_markup_and_rejects_unsafe_apply_links():
    readme = """<!-- ENTRY_JOBS:START -->
### Tier 1
| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Example | Software Engineer I <script>alert(1)</script> | Seattle, WA | 1 year | today | now |  | [Apply](javascript:alert(1)) |
### Tier 2
No matching roles in this tier right now.
### Tier 3
No matching roles in this tier right now.
<!-- ENTRY_JOBS:END -->
"""
    html = render_page(readme)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "javascript:" not in html
    assert "No matching roles in this tier right now." in html


def test_location_embedded_in_role_is_rendered_once():
    readme = """<!-- ENTRY_JOBS:START -->
### Tier 1
| Company | Role | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Example | Software Engineer I<br><sub>Seattle, WA</sub> | 1 year | today | now |  | [Apply](https://jobs.example/1) |
### Tier 2
No matching roles in this tier right now.
### Tier 3
No matching roles in this tier right now.
<!-- ENTRY_JOBS:END -->
"""
    html = render_page(readme)
    assert html.count(">Seattle, WA</p>") == 1


def test_table_split_keeps_escaped_pipes_in_a_role():
    assert split_row(r"| Acme | C\|C++ Engineer | 1 year | 2026-09-27 | now |  | [Apply](https://example.com) |") == [
        "Acme", "C|C++ Engineer", "1 year", "2026-09-27", "now", "",
        "[Apply](https://example.com)",
    ]


def test_page_keeps_tech_roles_when_experience_or_location_needs_review():
    eligible = {
        "role": "Software Engineer I",
        "experience": "1–2 years",
        "location": "Seattle, WA",
    }
    assert _qualifies_for_page(eligible)
    assert _qualifies_for_page({**eligible, "experience": "Not stated"})
    assert _qualifies_for_page({**eligible, "experience": "3+ years"})
    assert not _qualifies_for_page({**eligible, "location": "London, UK"})
    assert not _qualifies_for_page({**eligible, "location": "Seattle"})
    assert not _qualifies_for_page({**eligible, "role": "Mobile Service Mechanic I"})
    assert not _qualifies_for_page({**eligible, "location": "⚠ Unknown location"})
    assert _qualifies_for_page({**eligible, "location": "Cambridge, MA"})
    assert _qualifies_for_page({**eligible, "role": "Senior Software Engineer"})


def test_unknown_locations_with_explicitly_foreign_apply_urls_are_excluded():
    base = {
        "role": "Software Engineer",
        "experience": "Not stated",
        "location": "⚠ Unknown location",
        "apply": "[Apply](https://example.wd1.myworkdayjobs.com/job/Bengaluru/Software_Engineer)",
    }
    assert not _qualifies_for_page(base)
    assert not _qualifies_for_page({**base, "apply": "[Apply](https://example.com/job/Toronto/engineer)"})
    assert not _qualifies_for_page({**base, "location": "Hyderabad, India", "apply": "[Apply](https://example.com/job/123)"})
    assert not _qualifies_for_page({**base, "apply": "[Apply](https://example.com/job/123)"})


def test_us_job_location_and_workday_company_fallbacks():
    assert has_us_url_signal("https://example.wd1.myworkdayjobs.com/External/job/US-Oregon-Hillsboro/role")
    assert has_us_url_signal("https://example.wd1.myworkdayjobs.com/External/job/McLean-VA/role")
    assert not has_us_url_signal("https://example.wd1.myworkdayjobs.com/External/job/Bengaluru/role")
    assert is_us_location("Cambridge, MA")
    assert not is_us_location("Cambridge, United Kingdom")
    assert not is_us_location("Nairobi, Nairobi City")
    assert not is_us_location("DE-Berlin-Trion Building")
    assert is_us_location("Portland, OR")
    assert not is_us_location("Portland")
    assert display_company("capitalone.wd12.myworkdayjobs.com|capitalone|Capital_One") == "Capital One"
    assert display_company("intel.wd1.myworkdayjobs.com|intel|External") == "Intel"


def test_filter_controls_and_card_metadata_are_rendered_for_offline_filtering():
    readme = """<!-- ENTRY_JOBS:START -->
### Tier 1
| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|---|
| Acme & Sons | Software Engineer I | Seattle, WA | 1–2 years | 2026-09-27 | 2 hours ago | $120k | [Apply](https://jobs.example/1) |
### Tier 2
| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|---|
| Tiny | Backend Engineer | Boston, MA | 3+ years | Not shown | 5 days ago |  | [Apply](https://jobs.example/2) |
### Tier 3
No matching roles in this tier right now.
<!-- ENTRY_JOBS:END -->
"""
    html = render_page(readme)

    for control_id in (
        "experience-filter", "posted-filter", "company-filter", "keyword-filter",
        "tier-filter", "salary-filter", "reset-filters", "visible-job-count",
    ):
        assert f'id="{control_id}"' in html
    assert 'data-company="Acme &amp; Sons"' in html
    assert 'data-experience="early"' in html
    assert 'data-posted="2026-09-27"' in html
    assert 'data-tier="Tier 1"' in html
    assert 'data-salary="yes"' in html
    assert 'data-posted=""' in html
    assert 'data-experience="three-plus"' in html
    assert 'data-salary="no"' in html
    assert "Posting-date filters use the employer’s posted date" in html
    assert "addEventListener" in html


def test_experience_filter_buckets_cover_common_labels_and_edge_cases():
    cases = {
        "New grad": "early",
        "0 years": "early",
        "1–2 years": "early",
        "2 years": "early",
        "2+ years": "two-plus",
        "3+ years": "three-plus",
        "3–5 years": "mid",
        "6+ years": "senior",
        "10 years": "senior",
        "Not stated": "unknown",
        "": "unknown",
        "experience varies": "unknown",
    }
    assert {value: experience_bucket(value) for value in cases} == cases


def test_dedicated_early_career_page_only_contains_explicit_zero_to_two_year_roles():
    early = {"role": "Software Engineer I", "experience": "1–2 years"}
    new_grad_unknown = {"role": "Software Engineer - New Grad", "experience": "Not stated"}
    cases = {
        **{str(index): is_early_career_job(job) for index, job in enumerate((early, new_grad_unknown))},
        "1+": is_early_career_job({"role": "Backend Engineer", "experience": "1+ years"}),
        "2+": is_early_career_job({"role": "Software Engineer", "experience": "2+ years"}),
        "3+": is_early_career_job({"role": "Software Engineer", "experience": "3+ years"}),
        "unstated": is_early_career_job({"role": "Software Engineer", "experience": "Not stated"}),
        "contradictory_new_grad": is_early_career_job({"role": "Software Engineer New Grad", "experience": "4 years"}),
        "senior_title_with_two_years": is_early_career_job({"role": "Senior Software Engineer", "experience": "2 years"}),
        "principal_title_with_two_years": is_early_career_job({"role": "Principal Data Engineer", "experience": "2 years"}),
        "level_three_title": is_early_career_job({"role": "Software Engineer III", "experience": "1 year"}),
        "junior_one_year": is_early_career_job({"role": "Junior Frontend Engineer", "experience": "1 year"}),
    }
    assert cases == {
        "0": True, "1": True, "1+": False, "2+": False, "3+": False,
        "unstated": False, "contradictory_new_grad": False,
        "senior_title_with_two_years": False, "principal_title_with_two_years": False,
        "level_three_title": False, "junior_one_year": True,
    }

    readme = """<!-- ENTRY_JOBS:START -->
### Tier 1
| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|---|
| A | Software Engineer I | Seattle, WA | 1–2 years | 2026-09-27 | 1 day ago |  | [Apply](https://jobs.example/1) |
| B | Software Engineer - New Grad | Boston, MA | Not stated | 2026-09-27 | 1 day ago |  | [Apply](https://jobs.example/2) |
| C | Backend Engineer | Austin, TX | 3+ years | 2026-09-27 | 1 day ago |  | [Apply](https://jobs.example/3) |
| D | Backend Engineer | Portland, OR | 2+ years | 2026-09-27 | 1 day ago |  | [Apply](https://jobs.example/4) |
### Tier 2
No matching roles in this tier right now.
### Tier 3
No matching roles in this tier right now.
<!-- ENTRY_JOBS:END -->
"""
    page = render_page(readme, early_career_only=True)
    assert "CareerOS New Grad & 0–2 Year U.S. Tech Jobs" in page
    assert "New Grad / 0–2 years only" in page
    assert "New Grad &amp; 0–2 Year Roles" not in page
    assert "All recent tech jobs" in page
    assert "Software Engineer I" in page
    assert "Software Engineer - New Grad" in page
    assert page.count('<article class="job"') == 2
    assert page.count('data-experience="early"') == 2
    assert "3+ years" not in page
    assert "2+ years" not in page
