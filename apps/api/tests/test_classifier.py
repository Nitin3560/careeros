import sys
from pathlib import Path
import pytest
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

def test_sponsorship_false_positives_and_true_positives():
    false_positive = [
        "We do not discriminate against any applicant based on military status, or other protected status.",
        "All qualified applicants will receive consideration for employment without regard to race, color, religion, marital status, citizenship.",
        "Military fellows and part-time employees are not eligible for benefits.",
        "We develop allied military capabilities with advanced technology.",
        "Program specifics are detailed in company policies and employee benefit guides, including our 401(k) program.",
    ]
    assert all(not classify_job("Software Engineer", text)["sponsorship_block"] for text in false_positive)
    cases = [
        ("We are unable to sponsor or take over sponsorship of an employment Visa at this time.", "no_sponsorship"),
        ("Active TS/SCI security clearance with agency appropriate polygraph.", "clearance"),
        ("To conform to U.S. export control regulations (ITAR), this position requires access to export controlled information.", "itar"),
    ]
    for text, rule in cases:
        result = classify_job("Software Engineer", text)
        assert result["sponsorship_block"] and result["sponsorship_rule"] == rule

def test_real_data_location_and_title_regressions():
    for location in ["Nairobi, Nairobi City", "Barcelona", "Paris", "Amsterdam", "Milan", "Sao Paulo", "São Paulo", "Romania", "Spain", "Philippines", "Taguig", "Noida", "Nairobi", "Kenya", "Italy", "South Africa", "Cambridge (UK context)", "Spain (Remote)", "Amsterdam HQ", "Americas"]:
        assert classify_job("Software Engineer", location=location)["location_class"] == "non_us"
    for title in ["CNC Machinist Programmer", "AI Trainer - Advanced Hindi Fluency", "AI Business Analyst", "Junior Statistical Programmer Analyst", "SMB AI Power User - Competitive Evaluations", "AI Workflows Engineer"]:
        assert classify_job(title)["is_tech_title"] is False
    assert classify_job("Principal Associate, Data Scientist")["is_senior_title"]
    assert classify_job("Applied Researcher 4")["is_senior_title"]

@pytest.mark.parametrize("title", [
    "Prin Software Engineer", "Software Engineering Mgr", "Full Stack Engineer 5",
    "Advisor - Lab Automation Software Engineer", "Principal Associate, Data Scientist",
    "Applied Researcher 4",
])
def test_required_senior_titles(title):
    assert classify_job(title)["is_senior_title"] is True

@pytest.mark.parametrize("title", [
    "Software Engineer (Entry-Level) - C++", "New Grad Software Engineer",
    "Lead Generation Specialist", "Package Manager Engineer",
    "Software Engineer I", "Junior Software Engineer", "Software Engineer II",
    "Software Engineer (Entry-Level) - C++",
])
def test_seniority_false_positives_and_exemptions(title):
    assert classify_job(title)["is_senior_title"] is False

@pytest.mark.parametrize("title", [
    "Mechanical Engineer", "Quality Engineer II", "Technical Curriculum Developer",
    "Mobile Primary Care Nurse Practitioner", "CNC Machinist Programmer",
    "AI Trainer", "AI Business Analyst", "Junior Statistical Programmer Analyst",
    "SMB AI Power User - Competitive Evaluations",
    "AI Workflows Engineer", "Mobile Primary Care Nurse Practitioner",
])
def test_required_non_tech_titles(title):
    assert classify_job(title)["is_tech_title"] is False

@pytest.mark.parametrize(("location", "expected"), [
    ("Nairobi, Nairobi City", "non_us"), ("Barcelona", "non_us"), ("Paris", "non_us"),
    ("Milan", "non_us"), ("Noida", "non_us"), ("São Paulo", "non_us"),
    ("Boston", "us"), ("Cambridge", "unknown"), ("Cambridge, UK", "non_us"),
    ("Remote in Berlin", "non_us"), ("2 Locations", "unknown"), ("Remote", "unknown"),
    ("Columbus, OH; Fort Belvoir, VA", "us"), (None, "unknown"),
    ("Lausanne, Vaud, Switzerland", "non_us"), ("Nairobi, Nairobi City", "non_us"),
    ("Spain (Remote)", "non_us"), ("Amsterdam HQ", "non_us"), ("Americas", "non_us"),
])
def test_location_acceptance_cases(location, expected):
    assert classify_job("Software Engineer", location=location)["location_class"] == expected

@pytest.mark.parametrize("location", ["Remote in Cambridge", "Remote in Portland", "Remote in Arlington", "San Francisco", "Palo Alto", "Cambridge, MA"])
def test_us_city_only_and_ambiguous_city_edges(location):
    expected = "us" if location in {"San Francisco", "Palo Alto", "Cambridge, MA"} else "unknown"
    assert classify_job("Software Engineer", location=location)["location_class"] == expected

@pytest.mark.parametrize("location", ["Exampletown, ma", "Exampletown, in", "Exampletown, or", "Remote in me"])
def test_lowercase_state_abbreviations_and_english_words_are_not_us(location):
    assert classify_job("Software Engineer", location=location)["location_class"] != "us"

@pytest.mark.parametrize("sentence", [
    "We are an equal opportunity employer and do not discriminate against applicants.",
    "We do not discriminate based on protected status.",
    "All applicants are considered without regard to race or citizenship.",
    "We are unable to sponsor or take over sponsorship of an employment Visa at this time.",
    "US Citizenship required.", "Active TS/SCI security clearance with agency appropriate polygraph.",
    "This position requires access to export controlled information.",
])
def test_sponsorship_sentence_decisions_are_auditable(sentence):
    result = classify_job("Software Engineer", sentence)
    if sentence.startswith(("We are an equal", "We do not discriminate", "All applicants")):
        assert result["sponsorship_block"] is False
    else:
        assert result["sponsorship_block"] is True
        assert result["sponsorship_evidence"] == sentence
        assert result["sponsorship_rule"] in {"no_sponsorship", "citizenship", "clearance", "itar"}

@pytest.mark.parametrize(("description", "years", "source"), [
    ("## Preferred Qualifications\n5+ years preferred", None, "none"),
    ("## Basic Qualifications\n3+ years of experience required", 3, "required_section"),
    ("## Requirements:\nBS in CS, graduating 2026", None, "none"),
    ("## About Us\nFounded in 1999\n## Requirements\n1 week on-call", None, "none"),
])
def test_experience_parser_required_and_irrelevant_numbers(description, years, source):
    result = classify_job("Software Engineer", description)
    assert result["min_years_required"] == years
    assert result["years_source"] == source

@pytest.mark.parametrize(("title", "subfield"), [
    ("Backend Software Engineer", "backend"), ("Frontend Developer", "frontend"),
    ("Full Stack Engineer", "fullstack"), ("Mobile Engineer", "mobile"),
    ("Machine Learning Engineer", "ml_ai"), ("Data Engineer", "data"),
    ("Cloud Platform Engineer", "infra_devops"), ("Security Engineer", "security"),
    ("Embedded Software Engineer", "embedded"), ("QA Engineer", "qa"),
])
def test_tech_subfield_is_specific(title, subfield):
    assert classify_job(title)["tech_subfield"] == subfield

@pytest.mark.parametrize(("title", "employment"), [
    ("Software Engineer Intern", "intern"), ("Software Engineering Co-op", "co_op"),
    ("Contract Software Developer", "contract"), ("Part-Time Developer", "part_time"),
    ("Software Engineer International", "full_time"), ("Software Engineer", "full_time"),
])
def test_employment_type_boundaries(title, employment):
    assert classify_job(title)["employment_type"] == employment

def test_parse_tier_tracks_headings_even_when_no_required_heading():
    assert classify_job("Software Engineer", "## About the team\nWe build tools")["parse_tier"] == 2
    assert classify_job("Software Engineer", "## Requirements:\n")["parse_tier"] == 1

def test_curly_apostrophe_required_heading_and_nonexperience_numbers():
    result=classify_job("Software Engineer", "## What We’re Looking For:\n3+ years experience.\n401(k), founded in 1999, and 1 week on-call.")
    assert result["min_years_required"] == 3 and result["parse_tier"] == 1

def test_multi_location_any_us_part_kept_as_us():
    assert classify_job("Software Engineer", location="London, UK; Columbus, OH")["location_class"] == "us"

@pytest.mark.parametrize("title", [
    "Software Engineer", "Software Developer", "SWE", "SDE I", "Backend Engineer",
    "Frontend Developer", "Full Stack Engineer", "iOS Engineer", "Android Developer",
    "Machine Learning Engineer", "AI Engineer", "Data Engineer", "Data Scientist",
    "DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer", "Platform Engineer",
    "Infrastructure Engineer", "Security Engineer", "Computer Vision Engineer", "NLP Engineer",
    "Embedded Software Engineer", "Firmware Engineer", "QA Engineer", "SDET", "Test Engineer",
])
def test_positive_software_and_adjacent_technical_titles(title):
    assert classify_job(title)["is_tech_title"] is True

def test_sponsorship_audit_exemptions_and_title_evidence():
    for sentence in [
        "All qualified applicants will receive consideration for employment without regard to race, color, religion, marital status, citizenship status.",
        "We sponsor H-1B visas.",
        "No clearance required.",
    ]:
        assert classify_job("Software Engineer", sentence)["sponsorship_block"] is False
    title_result=classify_job("Data Engineer - CLEARED")
    assert title_result["sponsorship_block"] and title_result["sponsorship_rule"] == "clearance"
    assert title_result["sponsorship_evidence"] == "Data Engineer - CLEARED"

def test_every_feed_exclusion_has_an_audit_reason_and_sponsorship_evidence():
    for title,description,location,reason in [
        ("Mechanical Engineer","","Boston","non_tech_title"),
        ("Senior Software Engineer","","Boston","senior_title"),
        ("Software Engineer","","Paris","non_us_location"),
        ("Software Engineer Intern","","Boston","employment_type_intern"),
        ("Software Engineer","Unable to sponsor candidates.","Boston","sponsorship_restriction"),
    ]:
        result=classify_job(title,description,location)
        assert reason in result["exclusion_reasons"]
        if reason=="sponsorship_restriction": assert result["sponsorship_evidence"]

def test_degree_alternatives_keep_the_minimum_and_both_alternatives():
    result=classify_job("Software Engineer", "## Basic Qualifications\nBS + 3 years or MS + 1 year")
    assert result["min_years_required"] == 1
    assert result["min_years_alternatives"] == ["BS + 3 years", "MS + 1 year"]
