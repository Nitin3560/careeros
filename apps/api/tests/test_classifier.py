import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from app.classification import classify_job

def test_titles_and_locations():
    assert classify_job("Prin Software Engineer")["is_senior_title"]
    assert not classify_job("New Grad Software Engineer")["is_senior_title"]
    assert classify_job("Full Stack Engineer 5")["is_senior_title"]
    assert not classify_job("Mechanical Engineer")["is_tech_title"]
    assert classify_job("Software Engineer", location="Boston")["location_class"] == "us"
    assert classify_job("Software Engineer", location="Cambridge")["location_class"] == "unknown"
    assert classify_job("Software Engineer", location="Cambridge, UK")["location_class"] == "non_us"

def test_sponsorship_and_required_years():
    blocked = classify_job("Data Engineer - CLEARED", "unable to sponsor now or in the future.\n## Basic Qualifications\n3+ years required")
    assert blocked["sponsorship_block"] and blocked["sponsorship_evidence"]
    assert blocked["min_years_required"] == 3
    assert classify_job("Software Engineer", "## Preferred Qualifications\n5+ years preferred")["min_years_required"] is None
