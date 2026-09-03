from app.services.skill_ontology import expanded_profile_terms, requirement_terms


def test_requirement_terms_splits_and_canonicalizes_aliases():
    assert {"typescript", "node.js"} <= requirement_terms("TS/Node")
    assert {"react", "typescript", "node.js", "javascript"} <= requirement_terms(
        "React.js, TypeScript, Node.js, and JavaScript"
    )


def test_specializations_satisfy_parent_not_reverse():
    fastapi_profile = expanded_profile_terms({"fastapi"})
    python_profile = expanded_profile_terms({"python"})

    assert "backend" in fastapi_profile
    assert "python" in fastapi_profile
    assert "fastapi" not in python_profile
