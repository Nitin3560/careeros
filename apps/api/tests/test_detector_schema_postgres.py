import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.detect_ats import KNOWN_BOARDS_SQL  # noqa: E402


DATABASE_URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif("postgresql" not in DATABASE_URL, reason="requires PostgreSQL")


def test_known_board_query_matches_migrated_schema():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(KNOWN_BOARDS_SQL)).fetchall()
            assert isinstance(rows, list)
    finally:
        engine.dispose()
