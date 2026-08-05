import json
import re

from app.services.ai_client import call_llm

TAILOR_SYSTEM_PROMPT = """You help tailor a candidate's resume for a specific job, without inventing anything.

Rules:
- Only use skills, experience, and evidence that already exist in the candidate profile provided.
- Never invent a skill, project, number, or qualification that isn't in the profile.
- Do not add outcomes or impact claims unless they are already stated in the profile.
- Suggest reordering, rewording, and emphasis changes, not new content.
- Reword by changing phrasing, not by appending new result or impact clauses.
- If the job requires something genuinely missing from the profile, say so honestly in "gaps" rather than pretending it's covered.
- Respond with ONLY valid JSON, no markdown formatting, no extra text.

Output this exact JSON shape:
{
  "priority_skills_to_emphasize": [<skill names from the profile, ordered by relevance to this job>],
  "bullet_rewrites": [
    {"original": <string, must match a highlight already in the profile>, "suggested": <reworded to emphasize relevance to this job, same facts only>}
  ],
  "sections_to_reorder": <short string describing suggested ordering, e.g. "Move Autonomy Labs internship above education">,
  "gaps": [<short strings, things the job wants that the profile genuinely doesn't show>]
}"""


def tailor_resume_for_job(profile_data: dict, job_title: str, job_description: str) -> dict:
    user_prompt = f"""CANDIDATE PROFILE:
{json.dumps(profile_data, indent=2)}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:1500]}

Suggest tailoring changes."""

    raw_output = call_llm(
        TAILOR_SYSTEM_PROMPT,
        user_prompt,
        provider_order=["groq", "gemini"],
        max_tokens=1000,
    )

    try:
        parsed = json.loads(raw_output)
        bullet_rewrites = list(parsed.get("bullet_rewrites") or [])[:5]
        return {
            "priority_skills_to_emphasize": list(
                parsed.get("priority_skills_to_emphasize") or []
            )[:8],
            "bullet_rewrites": [_ground_rewrite(item) for item in bullet_rewrites],
            "sections_to_reorder": parsed.get("sections_to_reorder") or "",
            "gaps": list(parsed.get("gaps") or [])[:5],
        }
    except json.JSONDecodeError:
        return {
            "priority_skills_to_emphasize": [],
            "bullet_rewrites": [],
            "sections_to_reorder": "",
            "gaps": [],
            "error": "Failed to parse model output",
            "raw_output": raw_output,
        }


def _ground_rewrite(item: dict) -> dict:
    original = item.get("original") or ""
    suggested = item.get("suggested") or original

    if not _is_grounded(original, suggested):
        suggested = original

    return {"original": original, "suggested": suggested}


def _is_grounded(original: str, suggested: str) -> bool:
    original_lower = original.lower()
    suggested_lower = suggested.lower()
    unsupported_terms = [
        "enhanc",
        "enabl",
        "capabilit",
        "rigorous",
        "perception",
        "autonomous vehicle",
        "autonomous system",
        "scalable",
        "comprehensive",
        "complex",
        "significant",
        "successful",
        "showcas",
        "improv",
        "optimiz",
        "increas",
        "reduc",
        "boost",
        "accelerat",
        "streamlin",
        "deliver",
        "achiev",
        "outcome",
        "impact",
    ]

    if any(term in suggested_lower and term not in original_lower for term in unsupported_terms):
        return False

    original_facts = _extract_facts(original)
    suggested_facts = _extract_facts(suggested)

    if not suggested_facts.issubset(original_facts):
        return False
    if not original_facts.issubset(suggested_facts):
        return False
    return True


def _extract_facts(text: str) -> set[str]:
    facts = set()
    facts.update(match.lower() for match in re.findall(r"\d+[\w%+-]*", text))
    for word in re.findall(r"[A-Za-z][A-Za-z0-9+#/.\-]*", text):
        stripped = word.strip(",.():;")
        if len(stripped) < 2:
            continue
        if stripped.isupper() or any(c.isdigit() for c in stripped) or (
            stripped[0].isupper() and stripped[1:].islower() is False
        ):
            facts.add(stripped.lower())
    return facts
