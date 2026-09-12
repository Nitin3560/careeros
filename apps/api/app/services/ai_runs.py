import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app import models


def start_ai_run(
    db: Session,
    run_type: str,
    model: str | None,
    prompt_version: str,
    prompt_input: str,
) -> models.AiRun:
    run = models.AiRun(
        run_type=run_type,
        model=model,
        prompt_version=prompt_version,
        input_hash=hashlib.sha256(prompt_input.encode("utf-8")).hexdigest(),
        status="started",
    )
    db.add(run)
    db.flush()
    return run


def finish_ai_run(
    db: Session,
    run: models.AiRun,
    *,
    raw_output: str | None = None,
    validated_output: dict | list | None = None,
    status: str = "succeeded",
    failure_reason: str | None = None,
) -> models.AiRun:
    run.raw_output = raw_output
    run.validated_output = validated_output
    run.status = status
    run.failure_reason = failure_reason
    run.completed_at = datetime.utcnow()
    db.flush()
    return run
