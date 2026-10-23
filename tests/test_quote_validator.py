"""
tests/test_quote_validator.py — Quote validator tests.
"""
import pytest
from pathlib import Path

from app.db import reset_db, get_conn
from app.importer import import_batch
from app.quote_validator import validate_call_quote, validate_meeting_turn

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture
def loaded_db(tmp_path):
    db_path = tmp_path / "test.db"
    reset_db(db_path)
    import_batch(str(DATA / "01_initial.json"), db_path=db_path)
    import_batch(str(DATA / "02_update.json"), db_path=db_path)
    return db_path


def test_invalid_quote_rejected(loaded_db):
    """A made-up quote should fail validation for a call record."""
    with get_conn(loaded_db) as conn:
        rows = conn.execute(
            "SELECT source_type, source_id FROM source_record "
            "WHERE source_type='call' AND has_usable_transcript=1 LIMIT 1"
        ).fetchall()
    if not rows:
        pytest.skip("No usable call transcripts available")

    row = rows[0]
    result = validate_call_quote(row["source_type"], row["source_id"],
                                 "THIS QUOTE DEFINITELY DOES NOT EXIST IN ANY TRANSCRIPT ANYWHERE",
                                 db_path=loaded_db)
    assert result["valid"] is False


def test_valid_quote_accepted(loaded_db):
    """A real quote from a call transcript should pass validation."""
    with get_conn(loaded_db) as conn:
        rows = conn.execute(
            """SELECT sr.source_type, sr.source_id, t.transcript_text
               FROM source_record sr
               JOIN transcript t ON t.source_type=sr.source_type AND t.source_id=sr.source_id
               WHERE sr.source_type='call' AND sr.has_usable_transcript=1
               AND t.transcript_text IS NOT NULL LIMIT 1"""
        ).fetchall()
    if not rows:
        pytest.skip("No usable call transcripts available")

    row = rows[0]
    # Extract first 20 chars of transcript as quote
    snippet = row["transcript_text"][:20].strip()
    if len(snippet) < 5:
        pytest.skip("Snippet too short")

    result = validate_call_quote(row["source_type"], row["source_id"], snippet, db_path=loaded_db)
    assert result["valid"] is True


def test_meeting_turn_in_range(loaded_db):
    """Turn 1 should always be valid for M07 after update."""
    with get_conn(loaded_db) as conn:
        m07 = conn.execute(
            "SELECT source_type, source_id FROM source_record WHERE record_ref='M07'"
        ).fetchone()
    if not m07:
        pytest.skip("M07 not found")

    result = validate_meeting_turn(m07["source_type"], m07["source_id"], 1, db_path=loaded_db)
    assert result["valid"] is True


def test_meeting_turn_out_of_range(loaded_db):
    """Turn 9999 should be invalid."""
    with get_conn(loaded_db) as conn:
        m07 = conn.execute(
            "SELECT source_type, source_id FROM source_record WHERE record_ref='M07'"
        ).fetchone()
    if not m07:
        pytest.skip("M07 not found")

    result = validate_meeting_turn(m07["source_type"], m07["source_id"], 9999, db_path=loaded_db)
    assert result["valid"] is False
