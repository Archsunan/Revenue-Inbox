"""
app/db.py — SQLite database layer.

Identity: (source_type, source_id) is the ONLY primary key.
record_ref is stored for display ONLY. Never used as a lookup key.
"""
import sqlite3
import json
import os
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"


def get_db_path() -> Path:
    return DB_PATH


def _connect(path: Path = None) -> sqlite3.Connection:
    p = path or DB_PATH
    conn = sqlite3.connect(str(p), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn(path: Path = None):
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS source_record (
    source_type         TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    record_ref          TEXT,
    batch_revision      INTEGER NOT NULL DEFAULT 0,
    payload_json        TEXT NOT NULL,
    transcript_status   TEXT NOT NULL,
    has_usable_transcript INTEGER NOT NULL DEFAULT 0,
    local_date_ist      TEXT NOT NULL,
    imported_at         TEXT NOT NULL,
    updated_at          TEXT,
    PRIMARY KEY (source_type, source_id)
);

CREATE TABLE IF NOT EXISTS transcript (
    source_type         TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    transcript_text     TEXT,
    turns_json          TEXT,
    unavailable_reason  TEXT,
    batch_revision      INTEGER NOT NULL,
    attached_at         TEXT NOT NULL,
    PRIMARY KEY (source_type, source_id),
    FOREIGN KEY (source_type, source_id)
        REFERENCES source_record(source_type, source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_run (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT,
    batch_revision  INTEGER,
    batch_file      TEXT,
    run_at          TEXT NOT NULL,
    inserted        INTEGER DEFAULT 0,
    updated         INTEGER DEFAULT 0,
    unchanged       INTEGER DEFAULT 0,
    skipped_older   INTEGER DEFAULT 0,
    warnings_json   TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS analysis (
    source_type             TEXT NOT NULL,
    source_id               TEXT NOT NULL,
    route                   TEXT NOT NULL,
    output_json             TEXT NOT NULL,
    origin                  TEXT NOT NULL,
    generated_from_revision INTEGER NOT NULL,
    stale                   INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    updated_at              TEXT,
    PRIMARY KEY (source_type, source_id, route),
    FOREIGN KEY (source_type, source_id)
        REFERENCES source_record(source_type, source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS route_assignment (
    source_type         TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    suggested_routes    TEXT,
    suggested_reason    TEXT,
    suggested_confidence TEXT,
    suggested_triggers  TEXT,
    manual_routes       TEXT,
    manual_set_at       TEXT,
    manual_set_by       TEXT DEFAULT 'manager',
    manual_reason       TEXT,
    manual_previous     TEXT,
    PRIMARY KEY (source_type, source_id),
    FOREIGN KEY (source_type, source_id)
        REFERENCES source_record(source_type, source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_state (
    source_type TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    state       TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (source_type, source_id),
    FOREIGN KEY (source_type, source_id)
        REFERENCES source_record(source_type, source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS data_quality_flag (
    source_type TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    flag_key    TEXT NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (source_type, source_id, flag_key),
    FOREIGN KEY (source_type, source_id)
        REFERENCES source_record(source_type, source_id) ON DELETE CASCADE
);
"""


def init_db(path: Path = None) -> None:
    """Create all tables if they don't exist."""
    with get_conn(path) as conn:
        conn.executescript(SCHEMA)


def reset_db(path: Path = None) -> None:
    """Drop all data (keep schema). Idempotent."""
    p = path or DB_PATH
    if p.exists():
        p.unlink()
    init_db(p)


def get_all_records(conn, source_type=None, rep_email=None, organizer_email=None,
                     route=None, review_state_filter=None, transcript_status=None):
    """Return records with optional filters, joined to route_assignment and review_state."""
    params = []
    where = ["1=1"]
    if source_type:
        where.append("sr.source_type = ?")
        params.append(source_type)
    if transcript_status:
        where.append("sr.transcript_status = ?")
        params.append(transcript_status)

    sql = f"""
    SELECT sr.source_type, sr.source_id, sr.record_ref, sr.batch_revision,
           sr.payload_json, sr.transcript_status, sr.has_usable_transcript,
           sr.local_date_ist, sr.imported_at, sr.updated_at,
           ra.suggested_routes, ra.suggested_reason, ra.suggested_confidence,
           ra.suggested_triggers, ra.manual_routes, ra.manual_set_at, ra.manual_reason,
           rv.state as review_state
    FROM source_record sr
    LEFT JOIN route_assignment ra ON ra.source_type = sr.source_type AND ra.source_id = sr.source_id
    LEFT JOIN review_state rv ON rv.source_type = sr.source_type AND rv.source_id = sr.source_id
    WHERE {' AND '.join(where)}
    ORDER BY sr.local_date_ist DESC, sr.source_type, sr.record_ref
    """
    rows = conn.execute(sql, params).fetchall()

    # Post-filter by rep/organizer email (stored in payload_json)
    if rep_email or organizer_email or route or review_state_filter:
        filtered = []
        for row in rows:
            p = json.loads(row['payload_json'])
            if rep_email and p.get('rep_email') != rep_email:
                continue
            if organizer_email and p.get('organizer_email') != organizer_email:
                continue
            if route:
                sr = json.loads(row['suggested_routes'] or '[]')
                mr = json.loads(row['manual_routes'] or 'null') or []
                effective = mr if mr else sr
                if route not in effective:
                    continue
            if review_state_filter and row['review_state'] != review_state_filter:
                continue
            filtered.append(row)
        return filtered
    return rows


def get_record(conn, source_type: str, source_id: str):
    return conn.execute(
        "SELECT * FROM source_record WHERE source_type=? AND source_id=?",
        (source_type, source_id)
    ).fetchone()


def get_transcript(conn, source_type: str, source_id: str):
    return conn.execute(
        "SELECT * FROM transcript WHERE source_type=? AND source_id=?",
        (source_type, source_id)
    ).fetchone()


def get_analyses(conn, source_type: str, source_id: str):
    return conn.execute(
        "SELECT * FROM analysis WHERE source_type=? AND source_id=?",
        (source_type, source_id)
    ).fetchall()


def get_route_assignment(conn, source_type: str, source_id: str):
    return conn.execute(
        "SELECT * FROM route_assignment WHERE source_type=? AND source_id=?",
        (source_type, source_id)
    ).fetchone()


def get_review_state(conn, source_type: str, source_id: str):
    return conn.execute(
        "SELECT * FROM review_state WHERE source_type=? AND source_id=?",
        (source_type, source_id)
    ).fetchone()


def get_data_quality_flags(conn, source_type: str, source_id: str):
    return conn.execute(
        "SELECT * FROM data_quality_flag WHERE source_type=? AND source_id=?",
        (source_type, source_id)
    ).fetchall()


def get_import_runs(conn, limit: int = 20):
    return conn.execute(
        "SELECT * FROM import_run ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def count_records(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM source_record").fetchone()[0]


def count_usable_transcripts(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM source_record WHERE has_usable_transcript=1"
    ).fetchone()[0]
