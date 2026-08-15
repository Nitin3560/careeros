from types import SimpleNamespace

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


def test_cache_validity_rejects_estimated_stale_or_wrong_prompt_version():
    valid = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=False,
    )
    estimated = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=True,
    )
    stale = SimpleNamespace(
        profile_version=1,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION,
        is_estimated=False,
    )
    old_prompt = SimpleNamespace(
        profile_version=2,
        prompt_version=job_matching.MATCHING_PROMPT_VERSION - 1,
        is_estimated=False,
    )

    assert job_matching.is_match_cache_valid(valid, 2)
    assert not job_matching.is_match_cache_valid(estimated, 2)
    assert not job_matching.is_match_cache_valid(stale, 2)
    assert not job_matching.is_match_cache_valid(old_prompt, 2)
    assert not job_matching.is_match_cache_valid(None, 2)
