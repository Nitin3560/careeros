from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_feed import collapse_duplicates, prettify_slug, render_html, resolve_display_name  # noqa: E402


NOW = datetime(2026, 9, 23, 15, tzinfo=timezone.utc)


def test_display_name_fallback_chain_and_workday_slug():
    assert resolve_display_name(" Acme Display ", "Registry Name", "acme") == "Acme Display"
    assert resolve_display_name(None, "Registry Name", "acme") == "Registry Name"
    assert resolve_display_name(None, None, "lilly.wd115.myworkdayjobs.com|lilly|LLY") == "Lilly"
    assert resolve_display_name("lilly.wd115.myworkdayjobs.com|lilly|LLY", None, "lilly") == "Lilly"
    assert prettify_slug("north-star_ai") == "North Star AI"


def test_duplicate_locations_use_earliest_posting_and_keep_location_count():
    common = {"company": "acme", "title": "Software Engineer", "content_hash": "hash"}
    rows = [
        {**common, "id": "later", "first_seen_at": NOW, "location": "Seattle, WA", "application_url": "https://example.test/later"},
        {**common, "id": "earliest", "first_seen_at": NOW - timedelta(hours=2), "location": "Austin, TX", "application_url": "https://example.test/earliest"},
        {**common, "id": "third", "first_seen_at": NOW - timedelta(hours=1), "location": "Boston, MA", "application_url": "https://example.test/third"},
    ]
    collapsed = collapse_duplicates(rows)
    assert len(collapsed) == 1
    assert collapsed[0]["id"] == "earliest"
    assert collapsed[0]["application_url"] == "https://example.test/earliest"
    assert collapsed[0]["location_count"] == 3
    rendered = render_html(rows, generated_at=NOW)
    assert "Austin, TX" in rendered and "+2 locations" in rendered
    assert 'href="https://example.test/earliest"' in rendered


def test_new_marker_respects_previous_feed_watermark():
    rows = [
        {"id": "old", "company": "a", "title": "Engineer", "content_hash": "1", "first_seen_at": NOW - timedelta(hours=2), "location": "Austin, TX", "location_class": "us", "is_new_grad_title": False, "min_years_required": None, "application_url": "https://example.test/old", "ats": "greenhouse"},
        {"id": "new", "company": "b", "title": "Engineer I", "content_hash": "2", "first_seen_at": NOW - timedelta(minutes=30), "location": "Remote", "location_class": "unknown", "is_new_grad_title": True, "min_years_required": 1, "application_url": "https://example.test/new", "ats": "lever"},
    ]
    html = render_html(rows, generated_at=NOW, last_generated_at=NOW - timedelta(hours=1))
    assert 'class="new">NEW</span>' in html
    assert html.count('class="new">NEW</span>') == 1
    assert "New grad" in html and "Unknown" in html
    assert "2h ago" in html and "30m ago" in html


def test_twenty_row_fixture_renders_a_single_self_contained_phone_friendly_feed():
    rows = []
    for index in range(20):
        rows.append({
            "id": str(index), "company": f"company-{index}", "title": f"Backend Engineer {index}",
            "first_seen_at": NOW - timedelta(minutes=index * 5), "location": "New York, NY",
            "location_class": "us", "is_new_grad_title": index == 0,
            "min_years_required": (None if index % 5 == 4 else index % 5), "application_url": f"https://jobs.example.test/{index}",
            "ats": "greenhouse", "content_hash": f"hash-{index}",
        })
    html = render_html(rows, generated_at=NOW)
    assert html.startswith("<!doctype html>")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "<style>" in html and "https://" not in html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert html.count('<article class="job">') == 20
    assert "CareerOS Daily Job Feed" in html
    assert "New grad" in html and "0-2 yrs" in html and "3+ yrs" in html and "Not stated" in html
    assert html.index("Backend Engineer 0") < html.index("Backend Engineer 19")
