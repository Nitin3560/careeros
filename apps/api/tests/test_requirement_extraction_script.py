import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import extract_all_requirements  # noqa: E402


def test_verify_rejects_non_verbatim_hard_requirement():
    state, note = extract_all_requirements.verify(
        {
            "type": "citizenship",
            "value": "US citizenship",
            "source_text": "Must be a US citizen",
        },
        "Applicants should be legally authorized to work in the United States.",
    )

    assert state == "REJECTED"
    assert note == "source_text not found verbatim in JD"


def test_verify_marks_hedged_consequential_requirement_ambiguous():
    state, note = extract_all_requirements.verify(
        {
            "type": "education",
            "value": "Bachelor's degree",
            "source_text": "Bachelor's degree preferred",
        },
        "Bachelor's degree preferred for this role.",
    )

    assert state == "AMBIGUOUS"
    assert note == "hedged: preferred"


def test_load_jobs_reprocesses_missing_or_stale_prompt_versions(monkeypatch):
    captured = {}

    class FakeResult:
        def fetchall(self):
            return []

    class FakeDb:
        def execute(self, sql, params):
            captured["sql"] = str(sql)
            captured["params"] = params
            return FakeResult()

        def close(self):
            return None

    monkeypatch.setattr(extract_all_requirements, "SessionLocal", lambda: FakeDb())

    assert extract_all_requirements.load_jobs(limit=500, retry_failed=False) == []
    assert "jr.job_id IS NULL OR jr.prompt_version < :prompt_version" in captured["sql"]
    assert captured["params"]["prompt_version"] == extract_all_requirements.PROMPT_VERSION
    assert captured["params"]["limit"] == 500


def test_parse_json_rejects_top_level_list():
    try:
        extract_all_requirements.parse_json("[]")
    except ValueError as exc:
        assert str(exc) == "top-level JSON response must be an object"
    else:
        raise AssertionError("expected ValueError")


def test_normalize_parsed_response_keeps_only_dict_items():
    parsed = extract_all_requirements.normalize_parsed_response(
        {
            "hard_requirements": [{"type": "skill"}, "bad"],
            "preferred": "bad",
            "disqualifiers": [{"value": "x"}, 42],
            "years_required": None,
        }
    )

    assert parsed["hard_requirements"] == [{"type": "skill"}]
    assert parsed["preferred"] == []
    assert parsed["disqualifiers"] == [{"value": "x"}]
    assert parsed["years_required"] == {"min": None, "max": None}
