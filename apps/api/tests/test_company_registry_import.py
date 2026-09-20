from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.models import AtsBoard, CompanyRegistry
from scripts.import_company_registry import import_rows


def test_company_registry_import_is_idempotent():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    AtsBoard.__table__.create(engine)
    CompanyRegistry.__table__.create(engine)
    rows = [{
        "company_name": "Acme", "careers_url": "https://acme.test/careers",
        "domain": "acme.test", "source_tags": "manual|regional", "priority": "2",
    }]
    with Session(engine) as db:
        assert import_rows(db, rows) == {"inserted": 1, "updated": 0, "skipped": 0}
        assert import_rows(db, rows) == {"inserted": 0, "updated": 0, "skipped": 1}
        assert db.query(CompanyRegistry).count() == 1
