from types import SimpleNamespace
from uuid import uuid4

from app.services import tailoring


def test_sweep_rejects_unsupported_metric():
    facts = [
        SimpleNamespace(
            id=uuid4(),
            fact_key="project",
            fact_value="Reduced API latency by tuning database indexes.",
            tier="OBSERVED",
            project="careeros",
        )
    ]

    violations = tailoring.sweep("Reduced latency by 40% with database indexes.", facts)

    assert violations
    assert violations[0].kind == "metric"
    assert violations[0].span == "40%"


def test_validate_bullet_rejects_sweep_violation(monkeypatch):
    facts = [
        SimpleNamespace(
            id=uuid4(),
            fact_key="project",
            fact_value="Reduced API latency by tuning database indexes.",
            tier="OBSERVED",
            project="careeros",
        )
    ]
    monkeypatch.setattr(tailoring, "decompose_claims", lambda text: [])

    result = tailoring.validate_bullet(
        {"text": "Reduced latency by 40% with database indexes."},
        facts,
    )

    assert result.status == "REJECTED"
    assert result.violations[0].span == "40%"
