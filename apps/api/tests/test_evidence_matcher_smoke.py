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
