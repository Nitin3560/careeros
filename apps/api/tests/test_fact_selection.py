from types import SimpleNamespace
from uuid import uuid4

from app.services import fact_selection


class FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *args):
        return self

    def first(self):
        return self.row


class FakeDb:
    def __init__(self, requirements):
        self.requirements = requirements

    def query(self, model):
        return FakeQuery(SimpleNamespace(requirements=self.requirements))


def fact(value, project, weight, usability="ACTIVE"):
    return SimpleNamespace(
        id=uuid4(),
        fact_key="skill",
        fact_value=value,
        tier="OBSERVED",
        project=project,
        project_weight=weight,
        usability=usability,
    )


def keyed_fact(key, value, weight=1):
    row = fact(value, None, weight)
    row.fact_key = key
    row.tier = "ATTESTED"
    return row


def test_blocked_fact_never_appears(monkeypatch):
    active = fact("FastAPI", "careeros", 5)
    blocked = fact("FastAPI", "careeros", 99, usability="BLOCKED")
    monkeypatch.setattr(
        fact_selection,
        "active_candidate_facts",
        lambda db: [row for row in [active, blocked] if row.usability == "ACTIVE"],
    )

    selected = fact_selection.select_facts_for_job(
        FakeDb({"preferred": [{"value": "FastAPI"}]}),
        uuid4(),
    )

    assert active in selected
    assert blocked not in selected


def test_careeros_fact_outranks_equal_twinguard_fact(monkeypatch):
    careeros = fact("FastAPI", "careeros", 5)
    twinguard = fact("FastAPI", "twinguard", 1)
    monkeypatch.setattr(
        fact_selection,
        "active_candidate_facts",
        lambda db: [twinguard, careeros],
    )

    selected = fact_selection.select_facts_for_job(
        FakeDb({"preferred": [{"value": "FastAPI"}]}),
        uuid4(),
        k=2,
    )

    assert selected[:2] == [careeros, twinguard]


def test_identity_and_resume_metrics_are_always_selected(monkeypatch):
    filler = [fact(f"other-{index}", "misc", 10) for index in range(5)]
    identity = keyed_fact("email", "nxr3560@mavs.uta.edu")
    metric = keyed_fact("resume_metric_careeros_latency", "Cut latency from 690 ms to 3.5 ms.")
    monkeypatch.setattr(
        fact_selection,
        "active_candidate_facts",
        lambda db: filler + [identity, metric],
    )

    selected = fact_selection.select_facts_for_job(
        FakeDb({"preferred": [{"value": "FastAPI"}]}),
        uuid4(),
        k=1,
    )

    assert identity in selected
    assert metric in selected
