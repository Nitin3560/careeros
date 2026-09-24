"""End-to-end runner regression using a temporary PostgreSQL jobs table."""
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.classification.classifier import VERSION  # noqa: E402
from classify_jobs import classify_pending_batches  # noqa: E402


TEST_DATABASE_URL = os.getenv("CAREEROS_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    "postgresql" not in TEST_DATABASE_URL or "asyncpg" in TEST_DATABASE_URL,
    reason="set CAREEROS_TEST_DATABASE_URL to a synchronous PostgreSQL test database",
)


def test_requery_batches_classify_later_rows_with_lower_uuid_values():
    engine = create_engine(TEST_DATABASE_URL)
    connection = engine.connect()
    connection.execute(text("""
        CREATE TEMP TABLE jobs (
            id uuid PRIMARY KEY, title text, description_text text, location text,
            first_seen_at timestamp without time zone, classifier_version integer,
            title_normalized text, is_tech_title boolean, tech_subfield text,
            is_senior_title boolean, seniority_level text, is_new_grad_title boolean,
            employment_type text, location_class text, location_reason text,
            sponsorship_block boolean, sponsorship_evidence text, sponsorship_rule text,
            min_years_required integer, min_years_alternatives jsonb, years_source text,
            parse_tier integer, exclusion_reasons text[], years_basis text
        ) ON COMMIT PRESERVE ROWS
    """))
    connection.commit()
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    random_ids = [uuid.uuid4() for _ in range(100)]
    lower_ids = [uuid.UUID(int=index + 1) for index in range(100)]
    inserted_ids = random_ids + lower_ids
    base = datetime.utcnow() - timedelta(hours=1)
    try:
        connection.execute(text("""
            INSERT INTO jobs (id, title, description_text, location, first_seen_at, classifier_version)
            VALUES (:id, 'Software Engineer I', 'Requirements: 1+ year of professional software engineering experience.', 'Austin, TX', :seen, NULL)
        """), [{"id": str(job_id), "seen": base} for job_id in random_ids])
        connection.commit()
        first = classify_pending_batches(TestSession, batch_size=31, report=lambda _message: None)
        assert first["classified"] == 100

        connection.execute(text("""
            INSERT INTO jobs (id, title, description_text, location, first_seen_at, classifier_version)
            VALUES (:id, 'Software Engineer I', 'Requirements: 1+ year of professional software engineering experience.', 'Austin, TX', :seen, NULL)
        """), [{"id": str(job_id), "seen": base + timedelta(minutes=1)} for job_id in lower_ids])
        connection.commit()
        second = classify_pending_batches(TestSession, batch_size=29, report=lambda _message: None)
        assert second["classified"] == 100

        remaining = connection.execute(text("SELECT count(*) FROM jobs WHERE classifier_version=:version"), {"version": VERSION}).scalar_one()
        assert remaining == 200
    finally:
        connection.rollback()
        connection.close()
        engine.dispose()
