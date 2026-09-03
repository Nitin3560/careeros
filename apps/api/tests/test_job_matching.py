from types import SimpleNamespace
from uuid import uuid4

from app.services import job_matching


def test_match_job_to_profile_parses_and_bounds_model_output(monkeypatch):
    monkeypatch.setattr(
        job_matching,
        "call_llm",
        lambda *args, **kwargs: """
        {
          "overall_score": 120,
          "strengths": ["ROS 2", "PX4", "Simulation", "Python", "Extra"],
          "missing": ["Safety", "Scale", "Vision", "Extra"],
          "confidence": "very high"
        }
        """,
    )

    result = job_matching.match_job_to_profile(
        {"skills": [{"name": "ROS 2"}]},
        "Robotics Engineer",
        "Build simulation tooling",
    )

    assert result == {
        "overall_score": 100,
        "strengths": ["ROS 2", "PX4", "Simulation", "Python"],
        "missing": ["Safety", "Scale", "Vision"],
        "confidence": "low",
    }


def test_match_job_to_profile_handles_malformed_json(monkeypatch):
    monkeypatch.setattr(job_matching, "call_llm", lambda *args, **kwargs: "not json")

    result = job_matching.match_job_to_profile({}, "Role", "Description")

    assert result["overall_score"] is None
    assert result["confidence"] == "low"
    assert result["error"] == "Failed to parse model output"


def test_build_search_keywords_filters_generic_highlight_terms():
    profile = {
        "preferred_roles": ["Robotics Software Engineer"],
        "skills": [{"name": "ROS 2"}, {"name": "PX4"}],
        "experience": [
            {
                "highlights": [
                    "Developed technical workflows for autonomous localization and sensor fusion"
                ]
            }
        ],
    }

    keywords = job_matching.build_search_keywords(profile)

    assert {"robotics", "software", "engineer", "ros", "px4"}.issubset(keywords)
    assert {"autonomous", "localization", "sensor", "fusion"}.issubset(keywords)
    assert "developed" not in keywords
    assert "technical" not in keywords
    assert "workflows" not in keywords


def test_build_title_search_keywords_keeps_role_signal_terms():
    profile = {
        "preferred_roles": [
            "Robotics Software Engineer",
            "Simulation Validation Engineer",
        ]
    }

    keywords = job_matching.build_title_search_keywords(profile)

    assert {"robotics", "simulation", "validation"}.issubset(keywords)
    assert "software" not in keywords
    assert "engineer" not in keywords


def test_cache_validity_rejects_estimated_stale_or_wrong_prompt_version():
    valid = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=False,
        overall_score=70,
    )
    estimated = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=True,
        overall_score=70,
    )
    stale = SimpleNamespace(
        profile_version=1,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=False,
        overall_score=70,
    )
    old_prompt = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION - 1,
        is_estimated=False,
        overall_score=70,
    )
    failed = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=False,
        overall_score=None,
    )

    assert job_matching.is_match_cache_valid(valid, 2)
    assert not job_matching.is_match_cache_valid(estimated, 2)
    assert not job_matching.is_match_cache_valid(stale, 2)
    assert not job_matching.is_match_cache_valid(old_prompt, 2)
    assert not job_matching.is_match_cache_valid(failed, 2)
    assert not job_matching.is_match_cache_valid(None, 2)


def test_get_cached_matches_returns_records_and_pending(monkeypatch):
    scored_job_id = uuid4()
    pending_job_id = uuid4()
    user_id = str(uuid4())
    jobs = [
        SimpleNamespace(
            id=scored_job_id,
            title="Robotics Engineer",
            company="waymo",
            location="Mountain View",
            application_url="https://example.com/1",
        ),
        SimpleNamespace(
            id=pending_job_id,
            title="Simulation Engineer",
            company="waymo",
            location="Mountain View",
            application_url="https://example.com/2",
        ),
    ]
    match = SimpleNamespace(
        job_id=scored_job_id,
        overall_score=72,
        strengths=["ROS 2"],
        missing=["Safety"],
        confidence="medium",
        is_estimated=True,
    )

    class FakeQuery:
        def filter(self, *args):
            return self

        def all(self):
            return [match]

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    monkeypatch.setattr(job_matching, "shortlist_jobs", lambda *args, **kwargs: jobs)

    results = job_matching.get_cached_matches(
        FakeDb(),
        user_id,
        SimpleNamespace(data={}, profile_version=1),
        page_size=2,
    )

    assert results[0]["job_id"] == str(scored_job_id)
    assert results[0]["match"]["overall_score"] == 72
    assert results[0]["match"]["estimated"] is True
    assert results[1]["job_id"] == str(pending_job_id)
    assert results[1]["match"]["overall_score"] is None
