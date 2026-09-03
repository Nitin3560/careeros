import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "run_adjudicator_experiment.py"
SPEC = importlib.util.spec_from_file_location("run_adjudicator_experiment_script", SCRIPT_PATH)
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_preselect_facts_uses_overlap_and_weight():
    facts = [
        {
            "id": "low",
            "key": "skill",
            "value": "Python backend",
            "project": "twinguard",
            "weight": 1,
            "terms": experiment.tokens("Python backend twinguard"),
        },
        {
            "id": "high",
            "key": "skill",
            "value": "Python backend",
            "project": "careeros",
            "weight": 5,
            "terms": experiment.tokens("Python backend careeros"),
        },
    ]

    selected = experiment.preselect_facts("Python backend experience", facts, limit=1)

    assert selected[0]["id"] == "high"


def test_apply_met_adjudication_only_moves_met_requirements():
    decision = experiment.matcher.Decision(
        action="REVIEW",
        matched=[],
        missing=["GraphQL", "AWS"],
        matched_weight=0,
        missing_weight=2,
    )

    updated = experiment.apply_met_adjudications(
        decision,
        [
            {"requirement": "GraphQL", "run1": {"verdict": "MET"}},
            {"requirement": "AWS", "run1": {"verdict": "PARTIAL"}},
        ],
    )

    assert updated.matched == ["GraphQL"]
    assert updated.missing == ["AWS"]
    assert updated.matched_weight == 1
    assert updated.missing_weight == 1
