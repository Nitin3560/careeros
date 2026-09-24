from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from log_feed_miss import make_dedupe_key  # noqa: E402
from manage_feed_company import normalize_company_key  # noqa: E402
from report_feed_coverage import miss_rate  # noqa: E402
from explain_feed_job import explain  # noqa: E402


def test_miss_key_is_stable_for_whitespace_case_and_url_slash():
    assert make_dedupe_key("Acme  Inc", "Software Engineer", "https://jobs.example/123/") == make_dedupe_key("acme inc", "software engineer", "https://jobs.example/123")
    assert make_dedupe_key("Acme", "Role A", None) != make_dedupe_key("Acme", "Role B", None)


def test_company_rule_key_matches_feed_normalization():
    assert normalize_company_key("A.C.M.E. Inc.") == "acmeinc"
    assert normalize_company_key("  ") == ""


def test_miss_rate_handles_zero_denominator_and_counts_checked_rows():
    assert miss_rate(0, 0) is None
    assert miss_rate(3, 20) == 0.15


def test_feed_explanation_lists_all_independent_exclusion_reasons():
    row = {
        "now": datetime(2026, 9, 23, tzinfo=timezone.utc), "location": "London, UK",
        "title": "Engineer", "display_company": "Example",
        "company_is_verified": False,
        "expired_at": "expired", "classifier_version": 1, "is_tech_title": False,
        "is_senior_title": True, "location_class": "non_us", "sponsorship_block": True,
        "employment_type": "intern", "min_years_required": 4, "application_url": None,
        "rule": "block", "first_seen_at": None,
    }
    reasons = explain(row, version=2)
    assert reasons == [
        "expired", "stale_or_unclassified", "not_tech_title", "senior_or_unknown_seniority",
        "non_us_or_unknown_location_class", "sponsorship_restricted", "not_full_time",
        "over_2_years", "missing_apply_url", "unsafe_or_invalid_apply_url", "company_blocklisted", "company_name_unverified", "missing_first_seen_at",
        "explicit_non_us_location_signal",
    ]
