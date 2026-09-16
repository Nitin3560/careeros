from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.greenhouse_filler import (
    GreenhouseFillHalt,
    answer_for_label,
    is_greenhouse_url,
    validate_before_typing,
    validate_immovable_question,
)


def fact(key, value):
    return SimpleNamespace(id=uuid4(), fact_key=key, fact_value=value)


def packet(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"pdf")
    return SimpleNamespace(
        id=uuid4(),
        status="ready",
        resume_path=str(resume),
        cover_letter="Dear Hiring Manager",
    )


def job(url="https://boards.greenhouse.io/spacex/jobs/8726225002"):
    return SimpleNamespace(application_url=url)


def good_facts():
    return [
        fact("full_name", "Nitin Singh Rathore"),
        fact("email", "nxr3560@mavs.uta.edu"),
        fact("phone", "+1 817 819 8146"),
        fact("linkedin", "https://www.linkedin.com/in/nitin-singh-rathore"),
        fact("github", "https://github.com/Nitin3560"),
        fact("portfolio", "https://nitinsinghrathore.us"),
        fact("requires_sponsorship", "true"),
        fact("us_person", "false"),
        fact("professional_swe_years", "1.66"),
    ]


def test_accepts_only_greenhouse_urls():
    assert is_greenhouse_url("https://boards.greenhouse.io/spacex/jobs/1")
    assert not is_greenhouse_url("https://jobs.lever.co/example/1")


def test_validate_before_typing_checks_immutables(tmp_path):
    values = validate_before_typing(packet(tmp_path), job(), good_facts())

    assert values["full_name"] == "Nitin Singh Rathore"
    assert values["email"] == "nxr3560@mavs.uta.edu"
    assert values["professional_swe_years"] == "1.66"


def test_validate_before_typing_halts_on_identity_mismatch(tmp_path):
    facts = good_facts()
    facts[1] = fact("email", "wrong@example.com")

    with pytest.raises(GreenhouseFillHalt, match="email"):
        validate_before_typing(packet(tmp_path), job(), facts)


def test_validate_before_typing_halts_on_non_greenhouse(tmp_path):
    with pytest.raises(GreenhouseFillHalt, match="not a Greenhouse"):
        validate_before_typing(packet(tmp_path), job("https://jobs.lever.co/x/y"), good_facts())


def test_answer_for_label_maps_identity_and_immovables(tmp_path):
    values = validate_before_typing(packet(tmp_path), job(), good_facts())
    p = packet(tmp_path)

    assert answer_for_label("First Name", values, p).value == "Nitin"
    assert answer_for_label("Last Name", values, p).value == "Singh Rathore"
    assert answer_for_label("Email", values, p).value == "nxr3560@mavs.uta.edu"
    assert answer_for_label("Will you now or in the future require sponsorship?", values, p).value == "Yes"
    assert answer_for_label("Are you a U.S. person?", values, p).value == "No"
    assert answer_for_label("Years of professional software experience", values, p).value == "1.66"


def test_immovable_validator_rejects_contradictory_answers(tmp_path):
    values = validate_before_typing(packet(tmp_path), job(), good_facts())

    with pytest.raises(GreenhouseFillHalt, match="sponsorship"):
        validate_immovable_question("Will you require sponsorship?", "No", values)
    with pytest.raises(GreenhouseFillHalt, match="us_person"):
        validate_immovable_question("Are you a U.S. person?", "Yes", values)
