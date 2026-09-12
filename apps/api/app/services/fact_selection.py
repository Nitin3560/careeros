import uuid

from sqlalchemy.orm import Session

from app import models
from app.services.candidate_evidence import active_candidate_facts
from app.services.skill_ontology import relation, requirement_terms

ALWAYS_INCLUDE_KEYS = {
    "degree",
    "education",
    "education:degree",
    "employment",
    "experience",
    "work_experience",
}


def _requirement_values(requirements: dict | None) -> list[str]:
    values = []
    for section in ("hard_requirements", "preferred"):
        for item in (requirements or {}).get(section, []) or []:
            if isinstance(item, dict):
                values.append(item.get("skill") or item.get("value") or item.get("source_text") or "")
            else:
                values.append(str(item))
    return [value for value in values if value]


def _terms_for_fact(fact: models.CandidateFact) -> set[str]:
    return requirement_terms(f"{getattr(fact, 'fact_key', '')} {getattr(fact, 'fact_value', '')}")


def _score_fact(fact: models.CandidateFact, job_terms: set[str]) -> int:
    score = 0
    fact_terms = _terms_for_fact(fact)
    best_relation = None
    for fact_term in fact_terms:
        for job_term in job_terms:
            current = relation(fact_term, job_term)
            if current == "equivalent":
                best_relation = "equivalent"
                break
            if current == "specialization" and best_relation is None:
                best_relation = "specialization"
        if best_relation == "equivalent":
            break

    if best_relation == "equivalent":
        score += 3
    elif best_relation == "specialization":
        score += 2

    score += max(1, int(getattr(fact, "project_weight", 1) or 1))
    if getattr(fact, "tier", "") == "OBSERVED":
        score += 1
    return score


def _is_always_include(fact: models.CandidateFact) -> bool:
    key = str(getattr(fact, "fact_key", "") or "").strip().lower()
    return key in ALWAYS_INCLUDE_KEYS or key.startswith("education:") or key.startswith("employment:")


def select_facts_for_job(
    db: Session,
    job_id: uuid.UUID,
    k: int = 30,
) -> list[models.CandidateFact]:
    """Facts the generator is allowed to see. Deterministic, no LLM."""
    requirement_row = (
        db.query(models.JobRequirement)
        .filter(models.JobRequirement.job_id == job_id)
        .first()
    )
    job_terms = set()
    if requirement_row:
        for value in _requirement_values(requirement_row.requirements):
            job_terms.update(requirement_terms(value))

    facts = active_candidate_facts(db)
    scored = [(_score_fact(fact, job_terms), fact) for fact in facts]
    scored.sort(
        key=lambda item: (
            -item[0],
            str(getattr(item[1], "project", "") or ""),
            str(getattr(item[1], "fact_key", "") or ""),
            str(getattr(item[1], "fact_value", "") or ""),
            str(getattr(item[1], "id", "")),
        )
    )

    selected = []
    seen = set()
    for _, fact in scored:
        if _is_always_include(fact) or len(selected) < k:
            fact_id = getattr(fact, "id", id(fact))
            if fact_id not in seen:
                selected.append(fact)
                seen.add(fact_id)

    return selected
