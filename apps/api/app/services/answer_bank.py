import hashlib
import math
import re

from sqlalchemy.orm import Session

from app import models

SIMILARITY_THRESHOLD = 0.85
EMBEDDING_DIMENSIONS = 768


def embed_question(question: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"[a-z0-9]+", question.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _coerce_embedding(value) -> list[float]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip("[]")
        return [float(part) for part in stripped.split(",") if part.strip()]
    return list(value)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def find_answer(db: Session, question: str, company: str | None) -> models.AnswerBank | None:
    """Embed the question, cosine search, return above threshold."""
    query_embedding = embed_question(question)
    rows = (
        db.query(models.AnswerBank)
        .filter(models.AnswerBank.approved.is_(True))
        .all()
    )
    best = None
    best_score = 0.0
    for row in rows:
        if row.tier == "company_specific" and row.company != company:
            continue
        score = _cosine(query_embedding, _coerce_embedding(row.embedding))
        if score > best_score:
            best = row
            best_score = score
    if best and best_score >= SIMILARITY_THRESHOLD:
        best.times_used += 1
        db.flush()
        return best
    return None


def store_answer(
    db: Session,
    question,
    answer,
    tier,
    archetype,
    company=None,
) -> models.AnswerBank:
    row = models.AnswerBank(
        question_text=question,
        archetype=archetype,
        embedding=embed_question(question),
        answer=answer,
        approved=False,
        tier=tier,
        company=company,
    )
    db.add(row)
    db.flush()
    return row


def length_variant(answer: str, variant: str) -> str:
    words = answer.split()
    if variant == "one sentence":
        first_sentence = re.split(r"(?<=[.!?])\s+", answer.strip())[0]
        return first_sentence
    if variant == "50 words":
        return " ".join(words[:50])
    if variant == "100 words":
        return " ".join(words[:100])
    if variant == "bullets":
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
        return "\n".join(f"- {sentence}" for sentence in sentences)
    return answer
