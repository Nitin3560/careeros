import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.services.ai_client import call_llm

SYSTEM_PROMPT = """You are a job-matching assistant. You compare a candidate's profile against a job description and produce a structured, honest assessment.

Rules:
- Only reference skills/experience that actually appear in the candidate profile. Never invent or assume qualifications.
- Be specific: cite the actual skill or experience that supports each strength.
- Respond with ONLY valid JSON, no markdown formatting, no extra text.

Output this exact JSON shape:
{
  "overall_score": <integer 0-100>,
  "strengths": [<short strings, max 4>],
  "missing": [<short strings, max 3>],
  "confidence": "high" | "medium" | "low"
}"""


def match_job_to_profile(profile_data: dict, job_title: str, job_description: str) -> dict:
    user_prompt = f"""CANDIDATE PROFILE:
{json.dumps(profile_data, indent=2)}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:1500]}

Assess the match."""

    raw_output = call_llm(SYSTEM_PROMPT, user_prompt)

    try:
        parsed = json.loads(raw_output)
        score = parsed.get("overall_score")
        if isinstance(score, int):
            score = max(0, min(100, score))
        else:
            score = None

        confidence = parsed.get("confidence")
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        return {
            "overall_score": score,
            "strengths": list(parsed.get("strengths") or [])[:4],
            "missing": list(parsed.get("missing") or [])[:3],
            "confidence": confidence,
        }
    except json.JSONDecodeError:
        return {
            "overall_score": None,
            "strengths": [],
            "missing": [],
            "confidence": "low",
            "error": "Failed to parse model output",
            "raw_output": raw_output,
        }


STOPWORDS = {"and", "or", "the", "in", "of", "a", "for", "to", "with", "at"}


def shortlist_jobs(db: Session, profile_data: dict, limit: int = 30) -> list[models.Job]:
    raw_terms = list(profile_data.get("preferred_roles", []))
    for skill in profile_data.get("skills", []):
        if isinstance(skill, dict) and skill.get("name"):
            raw_terms.append(skill["name"])

    keywords = set()
    for term in raw_terms:
        for word in term.split():
            word = word.strip(",.()").lower()
            if len(word) > 2 and word not in STOPWORDS:
                keywords.add(word)

    if not keywords:
        return []

    conditions = []
    for kw in keywords:
        pattern = f"%{kw}%"
        conditions.append(models.Job.title.ilike(pattern))
        conditions.append(models.Job.description_text.ilike(pattern))

    return (
        db.query(models.Job)
        .filter(or_(*conditions))
        .order_by(models.Job.retrieved_at.desc())
        .limit(limit)
        .all()
    )
