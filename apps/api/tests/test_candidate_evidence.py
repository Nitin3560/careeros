from datetime import date
from types import SimpleNamespace

from app.services import candidate_evidence


def test_parse_fact_value_converts_booleans():
    assert candidate_evidence.parse_fact_value("true") is True
    assert candidate_evidence.parse_fact_value("false") is False
    assert candidate_evidence.parse_fact_value("India") == "India"


def test_compute_professional_swe_years_from_employment_rows():
    rows = [
        SimpleNamespace(
            employment_type="internship",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        ),
        SimpleNamespace(
            employment_type="education",
            start_date=date(2022, 1, 1),
            end_date=date(2026, 1, 1),
        ),
    ]

    class FakeQuery:
        def filter(self, *args):
            return self

        def all(self):
            return rows

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    years = candidate_evidence.compute_professional_swe_years(
        FakeDb(),
        "user-id",
        as_of=date(2026, 1, 1),
    )

    assert years == 1.0
