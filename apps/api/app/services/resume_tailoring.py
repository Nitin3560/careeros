from app.services.tailoring import generate_bullets


def tailor_resume_for_job(profile_data: dict, job_title: str, job_description: str) -> dict:
    facts = []
    for index, skill in enumerate(profile_data.get("skills", []) or []):
        if isinstance(skill, dict) and skill.get("name"):
            facts.append(
                type(
                    "ProfileFact",
                    (),
                    {
                        "id": f"00000000-0000-0000-0000-{index + 1:012d}",
                        "fact_key": "skill",
                        "fact_value": skill["name"],
                        "tier": "ATTESTED",
                        "project": None,
                    },
                )()
            )
    job = type(
        "JobContext",
        (),
        {"title": job_title, "company": "", "description_text": job_description},
    )()
    try:
        bullets, raw_output = generate_bullets(job, {}, facts)
    except Exception as exc:
        return {
            "priority_skills_to_emphasize": [],
            "bullet_rewrites": [],
            "sections_to_reorder": "",
            "gaps": [],
            "error": str(exc),
        }

    return {
        "priority_skills_to_emphasize": [
            fact.fact_value for fact in facts[:8]
        ],
        "bullet_rewrites": [
            {"original": "", "suggested": bullet["text"]} for bullet in bullets[:5]
        ],
        "sections_to_reorder": "",
        "gaps": [],
        "raw_output": raw_output,
    }
