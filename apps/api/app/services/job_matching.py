import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import desc, func, literal_column, or_
from sqlalchemy.orm import Session

from app import models
from app.services.ai_client import call_llm

MATCHING_PROMPT_VERSION = 1

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

    raw_output = call_llm(
        SYSTEM_PROMPT,
        user_prompt,
        provider_order=["gemini", "groq"],
    )

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
TITLE_WEIGHT = 3
DESCRIPTION_WEIGHT = 1
MIN_MATCH_SCORE = 3
GENERIC_TERMS = {
    "technical",
    "developed",
    "built",
    "integrated",
    "created",
    "using",
    "managed",
    "led",
    "improved",
    "improving",
    "supported",
    "maintained",
    "restructuring",
    "documentation",
    "automating",
    "workflows",
    "testing",
    "deployment",
    "program",
    "solutions",
    "operations",
    "systems",
    "responsible",
    "worked",
    "helped",
    "assisted",
    "various",
    "multiple",
    "ensured",
    "provided",
    "designed",
    "implemented",
    "collaborated",
}


def shortlist_jobs(
    db: Session, profile_data: dict, limit: int = 30, offset: int = 0
) -> list[models.Job]:
    scored = get_scored_matching_jobs(db, profile_data, limit=limit, offset=offset)
    return [job for job, score in scored]


def count_matching_jobs(db: Session, profile_data: dict) -> int:
    keywords = build_title_search_keywords(profile_data)
    if not keywords:
        return 0

    if _is_postgresql_session(db):
        search_vector = build_postgres_title_search_vector()
        search_query = build_postgres_search_query(keywords)
        return db.query(models.Job).filter(search_vector.op("@@")(search_query)).count()

    return len(_score_matching_jobs_in_python(db, keywords))


def get_scored_matching_jobs(
    db: Session,
    profile_data: dict,
    limit: int | None = None,
    offset: int = 0,
) -> list[tuple]:
    keywords = build_search_keywords(profile_data)
    title_keywords = build_title_search_keywords(profile_data)
    if title_keywords:
        keywords = title_keywords

    if not keywords:
        return []

    if not _is_postgresql_session(db):
        scored = _score_matching_jobs_in_python(db, keywords)
        return scored[offset : offset + limit] if limit is not None else scored[offset:]

    search_vector = build_postgres_title_search_vector()
    search_query = build_postgres_search_query(keywords)
    score_expr = func.ts_rank_cd(search_vector, search_query).label("match_score")
    query = (
        db.query(models.Job, score_expr)
        .filter(search_vector.op("@@")(search_query))
        .order_by(desc(score_expr), models.Job.retrieved_at.desc())
        .offset(offset)
    )
    if limit is not None:
        query = query.limit(limit)

    return query.all()


def build_search_keywords(profile_data: dict) -> set[str]:
    keywords = set()

    for term in profile_data.get("preferred_roles", []):
        for word in term.split():
            word = word.strip(",.()").lower()
            if len(word) > 2 and word not in STOPWORDS:
                keywords.add(word)

    for skill in profile_data.get("skills", []):
        if isinstance(skill, dict) and skill.get("name"):
            for word in skill["name"].split():
                word = word.strip(",.()").lower()
                if len(word) > 2 and word not in STOPWORDS:
                    keywords.add(word)

    for exp in profile_data.get("experience", []):
        if not isinstance(exp, dict):
            continue
        for highlight in exp.get("highlights", []):
            for word in highlight.split():
                word = word.strip(",.()").lower()
                if (
                    len(word) > 4
                    and word not in STOPWORDS
                    and word not in GENERIC_TERMS
                ):
                    keywords.add(word)

    return keywords


def build_title_search_keywords(profile_data: dict) -> set[str]:
    keywords = set()
    broad_title_terms = {"engineer", "developer", "scientist", "software", "systems"}

    for term in profile_data.get("preferred_roles", []):
        for word in term.split():
            word = word.strip(",.()").lower()
            if (
                len(word) > 2
                and word not in STOPWORDS
                and word not in GENERIC_TERMS
                and word not in broad_title_terms
            ):
                keywords.add(word)

    return keywords


def build_search_conditions(keywords: set[str]):
    conditions = []
    for kw in keywords:
        pattern = f"%{kw}%"
        conditions.append(models.Job.title.ilike(pattern))
        conditions.append(models.Job.description_text.ilike(pattern))
    return conditions


def build_postgres_title_search_vector():
    english = literal_column("'english'")
    return func.to_tsvector(english, func.coalesce(models.Job.title, ""))


def build_postgres_search_query(keywords: set[str]):
    english = literal_column("'english'")
    query_text = " OR ".join(sorted(keywords))
    return func.websearch_to_tsquery(english, query_text)


def _score_matching_jobs_in_python(db: Session, keywords: set[str]) -> list[tuple]:
    conditions = build_search_conditions(keywords)
    candidates = db.query(models.Job).filter(or_(*conditions)).all()

    scored = []
    for job in candidates:
        title_lower = (job.title or "").lower()
        desc_lower = (job.description_text or "").lower()
        title_hits = sum(1 for kw in keywords if kw in title_lower)
        desc_hits = sum(1 for kw in keywords if kw in desc_lower)
        score = title_hits * TITLE_WEIGHT + desc_hits * DESCRIPTION_WEIGHT
        if score >= MIN_MATCH_SCORE:
            scored.append((job, score))

    scored.sort(key=lambda pair: -pair[1])
    return scored


def _is_postgresql_session(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def fallback_match_score(profile_data: dict, job_title: str, job_description: str) -> dict:
    keywords = set()
    for skill in profile_data.get("skills", []):
        if isinstance(skill, dict) and skill.get("name"):
            keywords.add(skill["name"].lower())
    for role in profile_data.get("preferred_roles", []):
        keywords.update(w.lower() for w in role.split() if len(w) > 2)

    text = f"{job_title} {job_description}".lower()
    matched = sorted(kw for kw in keywords if kw in text)
    score = min(100, len(matched) * 15) if matched else 5

    return {
        "overall_score": score,
        "strengths": matched[:4],
        "missing": [],
        "confidence": "low",
    }


def get_or_create_matches(
    db: Session,
    user_id: str,
    profile: models.CandidateProfile,
    offset: int = 0,
    page_size: int = 10,
) -> list[dict]:
    profile_data = profile.data
    current_profile_version = profile.profile_version
    jobs = shortlist_jobs(db, profile_data, limit=page_size, offset=offset)
    job_ids = [job.id for job in jobs]
    existing_matches = (
        db.query(models.JobMatch)
        .filter(
            models.JobMatch.user_id == user_id,
            models.JobMatch.job_id.in_(job_ids),
        )
        .all()
        if job_ids
        else []
    )
    existing_by_job_id = {match.job_id: match for match in existing_matches}

    results = []
    jobs_to_score = []
    for job in jobs:
        existing = existing_by_job_id.get(job.id)
        if is_match_cache_valid(existing, current_profile_version):
            results.append(_format_match_result(job, _match_from_record(existing)))
        else:
            jobs_to_score.append(job)

    scored = []

    def score_job(job: models.Job) -> tuple[models.Job, dict]:
        try:
            match = match_job_to_profile(
                profile_data, job.title, job.description_text or ""
            )
            match["estimated"] = False
        except Exception:
            match = fallback_match_score(
                profile_data, job.title, job.description_text or ""
            )
            match["estimated"] = True
        return job, match

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(score_job, job) for job in jobs_to_score]
        for future in as_completed(futures):
            scored.append(future.result())

    for job, match in scored:
        existing = existing_by_job_id.get(job.id)
        if existing:
            existing.overall_score = match.get("overall_score")
            existing.strengths = match.get("strengths", [])
            existing.missing = match.get("missing", [])
            existing.confidence = match.get("confidence")
            existing.profile_version = current_profile_version
            existing.prompt_version = MATCHING_PROMPT_VERSION
            existing.is_estimated = match.get("estimated", False)
        else:
            db.add(
                models.JobMatch(
                    user_id=user_id,
                    job_id=job.id,
                    profile_version=current_profile_version,
                    prompt_version=MATCHING_PROMPT_VERSION,
                    overall_score=match.get("overall_score"),
                    strengths=match.get("strengths", []),
                    missing=match.get("missing", []),
                    confidence=match.get("confidence"),
                    is_estimated=match.get("estimated", False),
                )
            )
        results.append(_format_match_result(job, match))

    if scored:
        db.commit()

    results.sort(
        key=lambda r: (
            r["match"].get("overall_score") is None,
            -(r["match"].get("overall_score") or 0),
        )
    )
    return results


def get_cached_matches(
    db: Session,
    user_id: str,
    profile: models.CandidateProfile,
    offset: int = 0,
    page_size: int = 10,
) -> list[dict]:
    profile_data = profile.data
    jobs = shortlist_jobs(db, profile_data, limit=page_size, offset=offset)
    job_ids = [job.id for job in jobs]
    existing_matches = (
        db.query(models.JobMatch)
        .filter(
            models.JobMatch.user_id == user_id,
            models.JobMatch.job_id.in_(job_ids),
            models.JobMatch.profile_version == profile.profile_version,
            models.JobMatch.prompt_version == MATCHING_PROMPT_VERSION,
        )
        .all()
        if job_ids
        else []
    )
    existing_by_job_id = {match.job_id: match for match in existing_matches}

    results = []
    for job in jobs:
        existing = existing_by_job_id.get(job.id)
        match = _match_from_record(existing) if existing else _pending_match()
        results.append(_format_match_result(job, match))

    results.sort(
        key=lambda r: (
            r["match"].get("overall_score") is None,
            -(r["match"].get("overall_score") or 0),
        )
    )
    return results


def is_match_cache_valid(record, profile_version: int) -> bool:
    return bool(
        record
        and record.profile_version == profile_version
        and record.prompt_version == MATCHING_PROMPT_VERSION
        and not record.is_estimated
    )


def _match_from_record(record: models.JobMatch) -> dict:
    return {
        "overall_score": record.overall_score,
        "strengths": record.strengths,
        "missing": record.missing,
        "confidence": record.confidence,
        "estimated": record.is_estimated,
    }


def _pending_match() -> dict:
    return {
        "overall_score": None,
        "strengths": [],
        "missing": [],
        "confidence": None,
        "estimated": False,
    }


def _format_match_result(job: models.Job, match: dict) -> dict:
    return {
        "job_id": str(job.id),
        "job_title": job.title,
        "company": job.company,
        "location": job.location,
        "application_url": job.application_url,
        "match": match,
    }
