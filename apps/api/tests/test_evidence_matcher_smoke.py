import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "test_evidence_matcher.py"
SPEC = importlib.util.spec_from_file_location("test_evidence_matcher_script", SCRIPT_PATH)
matcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matcher)


def test_verified_missing_skill_routes_to_review_not_skip_hard():
    profile = {
        "skills": [{"name": "Python"}],
        "experience": [],
        "education": [{"degree": "B.S. Computer Science"}],
        "preferred_roles": [],
    }
    requirements = {
        "hard_requirements": [
            {
                "type": "skill",
                "skill": "Kubernetes",
                "verification_state": "VERIFIED",
                "source_text": "Experience with Kubernetes is required.",
            }
        ],
        "preferred": [],
        "years_required": {"min": None},
    }

    decision = matcher.evaluate(profile, requirements, attested={}, years=1)

    assert decision.action == "REVIEW"
    assert decision.blocked_by == []
    assert decision.review_reasons == ["missing_profile_fact_or_exact_match"]


def test_verified_clearance_contradiction_skips_hard():
    profile = {"skills": [], "experience": [], "education": [], "preferred_roles": []}
    requirements = {
        "hard_requirements": [
            {
                "type": "clearance",
                "value": "Active security clearance",
                "verification_state": "VERIFIED",
                "source_text": "Active security clearance is required.",
            }
        ],
        "preferred": [],
        "years_required": {"min": None},
    }

    decision = matcher.evaluate(profile, requirements, attested={"security_clearance": "none"}, years=1)

    assert decision.action == "SKIP_HARD"
    assert decision.blocked_by == ["Active security clearance"]


def test_verified_us_person_requirement_skips_hard():
    profile = {"skills": [], "experience": [], "education": [], "preferred_roles": []}
    requirements = {
        "hard_requirements": [
            {
                "type": "citizenship",
                "value": "U.S. Person",
                "verification_state": "VERIFIED",
                "source_text": "Must be a U.S. Person due to required access to U.S. export controlled information or facilities",
            }
        ],
        "preferred": [],
        "years_required": {"min": None},
    }

    decision = matcher.evaluate(
        profile,
        requirements,
        attested={"citizenship": "India", "us_person": False},
        years=1,
    )

    assert decision.action == "SKIP_HARD"
    assert decision.blocked_by == ["U.S. Person"]


def test_company_policy_routes_to_review_without_verified_job_gate():
    decision = matcher.evaluate(
        {"skills": [{"name": "Python", "weight": 5}], "experience": []},
        {"hard_requirements": [], "preferred": [{"skill": "Python"}]},
        attested={"us_person": False},
        years=1,
        job_context={"title": "Software Engineer", "company": "andurilindustries"},
    )

    assert decision.action == "REVIEW"
    assert decision.blocked_by == []
    assert "company_defense_or_export_control_risk" in decision.review_reasons


def test_role_family_and_seniority_shape_sorting():
    junior_backend = matcher.evaluate(
        {"skills": [{"name": "FastAPI", "weight": 5}], "experience": []},
        {"hard_requirements": [], "preferred": [{"skill": "FastAPI"}]},
        years=1,
        job_context={"title": "Backend Software Engineer", "company": "example"},
    )
    senior_security = matcher.evaluate(
        {"skills": [{"name": "Python", "weight": 5}], "experience": []},
        {"hard_requirements": [], "preferred": [{"skill": "Python"}]},
        years=1,
        job_context={"title": "Senior Application Security Engineer", "company": "example"},
    )

    assert junior_backend.role_family == "backend"
    assert senior_security.role_family == "security"
    assert senior_security.seniority_penalty == 2
    assert matcher.fit_sort_key(({}, junior_backend)) > matcher.fit_sort_key(({}, senior_security))


def test_willing_to_relocate_satisfies_location_requirement():
    decision = matcher.evaluate(
        {"skills": [{"name": "Python", "weight": 5}], "experience": []},
        {
            "hard_requirements": [
                {
                    "type": "location",
                    "value": "San Francisco, CA",
                    "verification_state": "VERIFIED",
                    "source_text": "This role is based in San Francisco, CA.",
                }
            ],
            "preferred": [{"skill": "Python"}],
            "years_required": {"min": None},
        },
        attested={"current_location": "Arlington, TX", "willing_to_relocate": True},
        years=1,
    )

    assert decision.action == "APPLY"
    assert decision.review_reasons == []


def test_load_db_items_returns_requirement_rows(monkeypatch):
    row = type(
        "Row",
        (),
        {
            "id": "job-id",
            "title": "Software Engineer",
            "company": "example",
            "location": "Remote",
            "requirements": {"hard_requirements": [], "preferred": []},
        },
    )()

    class FakeResult:
        def fetchall(self):
            return [row]

    class FakeDb:
        def execute(self, sql, params):
            return FakeResult()

        def close(self):
            return None

    monkeypatch.setattr(matcher, "SessionLocal", lambda: FakeDb())

    assert matcher.load_db_items(limit=20) == [
        {
            "job_id": "job-id",
            "title": "Software Engineer",
            "company": "example",
            "location": "Remote",
            "requirements": {"hard_requirements": [], "preferred": []},
        }
    ]


def test_load_profile_refuses_empty_candidate_facts(monkeypatch):
    class FakeDb:
        def close(self):
            return None

    monkeypatch.setattr(matcher, "SessionLocal", lambda: FakeDb())
    monkeypatch.setattr(matcher, "load_candidate_fact_profile", lambda db, user_id: {})
    monkeypatch.setattr(matcher, "has_candidate_evidence", lambda profile: False)

    try:
        matcher.load_profile("user-id")
    except SystemExit as exc:
        assert "candidate_facts is empty" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_load_profile_can_use_legacy_profile_when_allowed(monkeypatch):
    row = type("Row", (), {"data": {"skills": []}, "status": "ACTIVE"})()

    class FakeResult:
        def first(self):
            return row

    class FakeDb:
        def execute(self, sql, params):
            return FakeResult()

        def close(self):
            return None

    monkeypatch.setattr(matcher, "SessionLocal", lambda: FakeDb())
    monkeypatch.setattr(matcher, "load_candidate_fact_profile", lambda db, user_id: {})
    monkeypatch.setattr(matcher, "has_candidate_evidence", lambda profile: False)

    assert matcher.load_profile("user-id", allow_legacy_profile=True) == {"skills": []}


def test_fit_sort_key_uses_project_weighted_matches():
    high_weight = matcher.evaluate(
        {"skills": [{"name": "FastAPI", "weight": 5}], "experience": []},
        {"hard_requirements": [], "preferred": [{"skill": "backend"}]},
    )
    low_weight = matcher.evaluate(
        {"skills": [{"name": "ROS2", "weight": 1}], "experience": []},
        {"hard_requirements": [], "preferred": [{"skill": "robotics"}]},
    )

    assert high_weight.matched_weight == 5
    assert low_weight.matched_weight == 1
    assert matcher.fit_sort_key(({}, high_weight)) > matcher.fit_sort_key(({}, low_weight))


def test_no_positive_signal_routes_to_review():
    decision = matcher.evaluate(
        {"skills": [], "experience": [], "preferred_roles": []},
        {"hard_requirements": [], "preferred": [], "years_required": {"min": 3}},
    )

    assert decision.action == "REVIEW"
    assert decision.review_reasons == ["no_positive_match_signal"]


def test_avoid_domain_routes_to_review():
    decision = matcher.evaluate(
        {"skills": [{"name": "Python", "weight": 5}], "experience": []},
        {"hard_requirements": [], "preferred": [{"skill": "Python"}]},
        attested={"avoid_domains": "robotics, defense"},
        job_context={"title": "Robotics Software Engineer", "company": "example"},
    )

    assert decision.action == "REVIEW"
    assert decision.avoid_domain_hits == ["robotics"]
    assert "avoid_domain_match" in decision.review_reasons


def test_btech_or_ms_satisfies_bachelor_requirement():
    decision = matcher.evaluate(
        {
            "skills": [{"name": "Python", "weight": 5}],
            "education": [
                {"degree": "M.S. Computer Science"},
                {"degree": "B.Tech Computer Science"},
            ],
            "experience": [],
        },
        {
            "hard_requirements": [
                {
                    "type": "education",
                    "value": "Bachelor's degree",
                    "verification_state": "VERIFIED",
                    "source_text": "Bachelor's degree in Computer Science or related field",
                }
            ],
            "preferred": [{"skill": "Python"}],
            "years_required": {"min": None},
        },
    )

    assert decision.action == "APPLY"
    assert decision.unresolved == []
