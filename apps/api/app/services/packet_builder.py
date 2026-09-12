import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.services.ai_runs import finish_ai_run, start_ai_run
from app.services.answer_bank import find_answer
from app.services.fact_selection import select_facts_for_job
from app.services.resume_export import generate_docx
from app.services.tailoring import generate_and_validate, generate_cover_letter, sweep

MIN_ACCEPTED_BULLETS = 3
IDENTITY_FACT_KEYS = {"full_name", "email"}
RESUME_OUTPUT_DIR = Path("generated/resumes")


def _requirements_for_job(db: Session, job_id: uuid.UUID) -> dict:
    row = (
        db.query(models.JobRequirement)
        .filter(models.JobRequirement.job_id == job_id)
        .first()
    )
    return row.requirements if row and row.requirements else {}


def _application_questions(requirements: dict) -> list[str]:
    questions = []
    for key in ("application_questions", "questions", "screening_questions"):
        values = requirements.get(key) or []
        for value in values:
            if isinstance(value, dict):
                text = value.get("question") or value.get("text") or value.get("value")
            else:
                text = str(value)
            if text:
                questions.append(text)
    return questions


def resolve_answers(db: Session, job, requirements: dict) -> tuple[dict, list[str]]:
    answers = {}
    missing = []
    for question in _application_questions(requirements):
        answer = find_answer(db, question, getattr(job, "company", None))
        if answer is None:
            missing.append(question)
        else:
            answers[question] = answer.answer
    return answers, missing


def render_resume(job, bullets: list[dict], facts) -> str:
    RESUME_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    identity = {fact.fact_key: fact.fact_value for fact in facts if fact.fact_key in IDENTITY_FACT_KEYS}
    skills = [
        {"name": fact.fact_value}
        for fact in facts
        if fact.fact_key in {"skill", "skills", "technology", "framework", "tool"}
    ][:16]
    education = [
        {"degree": fact.fact_value, "institution": "", "year": ""}
        for fact in facts
        if fact.fact_key.startswith("education") or fact.fact_key == "degree"
    ]
    content = {
        "full_name": identity.get("full_name") or "Candidate",
        "summary": f"Tailored for {getattr(job, 'title', 'role')} at {getattr(job, 'company', 'company')}.",
        "skills": skills,
        "experience": [
            {
                "title": "Selected experience",
                "company": "Evidence-backed profile",
                "duration": "",
                "highlights": [bullet["text"] for bullet in bullets],
            }
        ],
        "education": education,
    }
    path = RESUME_OUTPUT_DIR / f"{job.id}.docx"
    path.write_bytes(generate_docx(content))
    return str(path)


def preflight(
    bullets: list[dict],
    cover_letter: str | None,
    answers: dict,
    resume_path: str | None,
    facts,
    missing_answers: list[str] | None = None,
) -> list[str]:
    missing = []
    if len(bullets) < MIN_ACCEPTED_BULLETS:
        missing.append(f"requires at least {MIN_ACCEPTED_BULLETS} accepted bullets")
    if not cover_letter:
        missing.append("cover letter missing")
    elif sweep(cover_letter, facts):
        missing.append("cover letter contains unsupported risk spans")
    for question in missing_answers or []:
        missing.append(f"unanswered application question: {question}")
    if not resume_path:
        missing.append("resume missing")
    elif not Path(resume_path).exists() or Path(resume_path).stat().st_size == 0:
        missing.append("resume file missing or empty")

    present_identity = {fact.fact_key for fact in facts if fact.fact_value}
    for key in sorted(IDENTITY_FACT_KEYS - present_identity):
        missing.append(f"attested identity field missing: {key}")
    return missing


def build_packet(db: Session, job_id, profile_version) -> models.ApplicationPacket:
    job_uuid = uuid.UUID(str(job_id))
    job = db.query(models.Job).filter(models.Job.id == job_uuid).first()
    if not job:
        raise ValueError(f"job not found: {job_id}")

    requirements = _requirements_for_job(db, job_uuid)
    facts = select_facts_for_job(db, job_uuid)
    if not facts:
        raise ValueError("no active facts available for packet generation")

    run_input = f"{job_uuid}:{profile_version}:{[str(fact.id) for fact in facts]}"
    ai_run = start_ai_run(db, "application_packet", None, "packet-builder-v1", run_input)

    bullets = []
    rejected = []
    cover_letter = None
    answers = {}
    resume_path = None
    status = "draft"
    blocked_reason = None
    try:
        bullets, raw_output, rejected = generate_and_validate(job, requirements, facts)
        cover_letter = generate_cover_letter(job, facts)
        answers, missing_answers = resolve_answers(db, job, requirements)
        resume_path = render_resume(job, bullets, facts)
        missing = preflight(bullets, cover_letter, answers, resume_path, facts, missing_answers)
        if rejected and len(rejected) > len(bullets):
            status = "rejected"
            blocked_reason = "more than half of generated bullets were rejected"
        else:
            status = "blocked" if missing else "ready"
            blocked_reason = "; ".join(missing) if missing else None
        finish_ai_run(
            db,
            ai_run,
            raw_output=raw_output,
            validated_output={"bullets": bullets, "rejected": rejected},
            status="succeeded",
        )
    except Exception as exc:
        status = "blocked"
        blocked_reason = str(exc)
        finish_ai_run(db, ai_run, status="failed", failure_reason=blocked_reason)

    packet = models.ApplicationPacket(
        job_id=job_uuid,
        profile_version=profile_version,
        fact_ids=[fact.id for fact in facts],
        bullets=bullets,
        cover_letter=cover_letter,
        answers=answers,
        resume_path=resume_path,
        status=status,
        blocked_reason=blocked_reason,
        rejected_claims=rejected,
        ai_run_id=ai_run.id,
    )
    db.add(packet)
    db.flush()
    return packet
