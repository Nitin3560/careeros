import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from render_entry_jobs_page import _qualifies_for_page, render_page, split_row  # noqa: E402
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

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "javascript:" not in html
    assert "No matching roles in this tier right now." in html


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
