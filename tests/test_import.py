"""
tests/test_import.py — Core import pipeline tests.
"""
import json
import random
from pathlib import Path
import pytest

from app.db import reset_db, get_conn, count_records, count_usable_transcripts, get_record
from app.importer import import_batch
from app.router import route_all

DATA = Path(__file__).parent.parent / "data"
INITIAL = str(DATA / "01_initial.json")
UPDATE = str(DATA / "02_update.json")


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    reset_db(p)
    return p


# ── 1. Initial import gives exactly 44 records ────────────
def test_initial_import_count(db_path):
    log = import_batch(INITIAL, db_path=db_path)
    with get_conn(db_path) as conn:
        total = count_records(conn)
    assert total == 44, f"Expected 44 after initial import, got {total}"
    assert log["inserted"] == 44
    assert log["updated"] == 0
    assert log["skipped_older"] == 0


# ── 2. Repeat import (same file) keeps 44 ─────────────────
def test_repeat_import_idempotent(db_path):
    import_batch(INITIAL, db_path=db_path)
    log2 = import_batch(INITIAL, db_path=db_path)
    with get_conn(db_path) as conn:
        total = count_records(conn)
    assert total == 44
    assert log2["inserted"] == 0
    assert log2["unchanged"] == 44


# ── 3. Shuffled import gives identical count ───────────────
def test_shuffled_import_count(db_path):
    import_batch(INITIAL, shuffle=True, db_path=db_path)
    with get_conn(db_path) as conn:
        total = count_records(conn)
    assert total == 44


# ── 4. Update import keeps 44, upgrades M07 transcript ────
def test_update_import(db_path):
    import_batch(INITIAL, db_path=db_path)

    with get_conn(db_path) as conn:
        usable_before = count_usable_transcripts(conn)

    log2 = import_batch(UPDATE, db_path=db_path)

    with get_conn(db_path) as conn:
        total = count_records(conn)
        usable_after = count_usable_transcripts(conn)

    assert total == 44, f"Count must stay 44 after update, got {total}"
    assert log2["updated"] == 1, f"Expected 1 updated (M07), got {log2['updated']}"
    assert log2["inserted"] == 0
    assert usable_after == usable_before + 1, \
        f"Expected 1 more usable transcript after update: {usable_before} -> {usable_after}"


# ── 5. Update skips older batch ───────────────────────────
def test_update_skips_older(db_path):
    import_batch(UPDATE, db_path=db_path)   # rev=2 first
    log = import_batch(INITIAL, db_path=db_path)  # rev=1 after
    assert log["skipped_older"] >= 1, "Should skip older revision record"


# ── 6. Coverage: 17/44 before update, 18/44 after ─────────
def test_coverage_numbers(db_path):
    import_batch(INITIAL, db_path=db_path)
    with get_conn(db_path) as conn:
        before = count_usable_transcripts(conn)
    assert before == 17, f"Expected 17 usable before update, got {before}"

    import_batch(UPDATE, db_path=db_path)
    with get_conn(db_path) as conn:
        after = count_usable_transcripts(conn)
    assert after == 18, f"Expected 18 usable after update, got {after}"


# ── 7. Identity: (source_type, source_id) as key ──────────
def test_identity_is_composite_key(db_path):
    import_batch(INITIAL, db_path=db_path)
    # Verify we can look up every record by (source_type, source_id)
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT source_type, source_id, record_ref FROM source_record").fetchall()
    assert len(rows) == 44
    for row in rows:
        with get_conn(db_path) as conn:
            rec = get_record(conn, row["source_type"], row["source_id"])
        assert rec is not None, f"Could not retrieve ({row['source_type']},{row['source_id']})"


# ── 8. Identity test: grep code for record_ref/name as key ─
def test_no_identity_misuse():
    """Fail if any non-display use of record_ref, name, or index as a lookup key."""
    bad_patterns = [
        "WHERE record_ref",
        "WHERE name",
        'get_record.*record_ref',
        'record_ref.*primary',
    ]
    import re
    src_dir = Path(__file__).parent.parent / "app"
    violations = []
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pat in bad_patterns:
            for m in re.finditer(pat, content, re.IGNORECASE):
                violations.append(f"{py_file.name}: {m.group(0)!r}")
    assert not violations, f"Identity misuse detected:\n" + "\n".join(violations)


# ── 9. Routing: route_all runs without error ───────────────
def test_route_all(db_path):
    import_batch(INITIAL, db_path=db_path)
    n = route_all(db_path=db_path)
    assert n == 44


# ── 10. Manual route survives repeat import + update + restart
def test_manual_route_persists(db_path):
    import json, datetime, pytz
    import_batch(INITIAL, db_path=db_path)
    route_all(db_path=db_path)

    # Get first record
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT source_type, source_id FROM source_record LIMIT 1").fetchone()
    st, sid = row["source_type"], row["source_id"]

    # Set manual route
    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()
    with get_conn(db_path) as conn:
        conn.execute("""
            UPDATE route_assignment SET manual_routes=?, manual_set_at=?
            WHERE source_type=? AND source_id=?
        """, (json.dumps(["customer_follow_up"]), now_str, st, sid))

    # Repeat import (same revision → unchanged)
    import_batch(INITIAL, db_path=db_path)

    # Update (different record — M07)
    import_batch(UPDATE, db_path=db_path)

    # Re-route (should not clear manual routes)
    route_all(db_path=db_path)

    with get_conn(db_path) as conn:
        ra = conn.execute(
            "SELECT manual_routes FROM route_assignment WHERE source_type=? AND source_id=?",
            (st, sid)
        ).fetchone()

    assert ra is not None
    assert ra["manual_routes"] is not None
    manual = json.loads(ra["manual_routes"])
    assert "customer_follow_up" in manual, f"Manual route lost: {manual}"


# ── 11. Stale flag on changed transcript ──────────────────
def test_stale_flag_on_transcript_change(db_path):
    import json, datetime, pytz
    import_batch(INITIAL, db_path=db_path)
    route_all(db_path=db_path)

    # Manually insert an analysis for M07 (which will be updated)
    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()
    # Find M07
    with get_conn(db_path) as conn:
        m07 = conn.execute(
            "SELECT source_type, source_id FROM source_record WHERE record_ref='M07'"
        ).fetchone()

    if m07 is None:
        pytest.skip("M07 not found")

    st, sid = m07["source_type"], m07["source_id"]

    with get_conn(db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO analysis
            (source_type, source_id, route, output_json, origin, generated_from_revision, stale, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (st, sid, "customer_follow_up",
              json.dumps({"summary": "test", "evidence": [], "generated_from_revision": 1}),
              "pre-generated", 1, 0, now_str))

    # Now import update (M07 transcript arrives)
    import_batch(UPDATE, db_path=db_path)

    with get_conn(db_path) as conn:
        a = conn.execute(
            "SELECT stale FROM analysis WHERE source_type=? AND source_id=?",
            (st, sid)
        ).fetchone()

    assert a is not None and a["stale"] == 1, "Analysis should be marked stale after transcript update"


# ── 12. Import log structure ───────────────────────────────
def test_import_log_structure(db_path):
    log = import_batch(INITIAL, db_path=db_path)
    for key in ("batch_id", "batch_revision", "inserted", "updated", "unchanged", "skipped_older", "warnings"):
        assert key in log, f"Missing key in import log: {key}"


# ── 13. Export engine runs and produces manifest ───────────
def test_export_functionality(db_path):
    from app.exporter import run_export
    import_batch(INITIAL, db_path=db_path)
    import_batch(UPDATE, db_path=db_path)
    route_all(db_path=db_path)
    res = run_export(db_path=db_path)
    assert res["total"] == 44
    assert Path(res["manifest_path"]).exists()
    assert Path(res["zip_path"]).exists()

