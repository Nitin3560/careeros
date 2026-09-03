import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "load_project_facts.py"
SPEC = importlib.util.spec_from_file_location("load_project_facts_script", SCRIPT_PATH)
loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loader)


def test_fact_rows_adds_project_weight_and_dedupes_skills():
    rows = loader.fact_rows(
        "careeros",
        {
            "facts": [
                {
                    "claim": "Built a FastAPI backend",
                    "tier": "OBSERVED",
                    "technologies": ["FastAPI", "Python", "FastAPI"],
                }
            ]
        },
    )

    assert rows == [
        {
            "fact_key": "project_fact",
            "fact_value": "Built a FastAPI backend",
            "tier": "OBSERVED",
            "source": "repo_extraction",
            "project": "careeros",
            "project_weight": 5,
        },
        {
            "fact_key": "skill",
            "fact_value": "FastAPI",
            "tier": "OBSERVED",
            "source": "repo_extraction",
            "project": "careeros",
            "project_weight": 5,
        },
        {
            "fact_key": "skill",
            "fact_value": "Python",
            "tier": "OBSERVED",
            "source": "repo_extraction",
            "project": "careeros",
            "project_weight": 5,
        },
    ]


def test_fact_rows_skips_conflicted_facts():
    rows = loader.fact_rows(
        "twinguard",
        {
            "facts": [
                {
                    "claim": "Configured but unused Redis",
                    "tier": "CONFLICTED",
                    "technologies": ["Redis"],
                }
            ]
        },
    )

    assert rows == []
