"""
app/importer.py — Batch import engine.

Conflict rule (evidence-based, Phase 0.5):
  - Revision is BATCH-LEVEL only (no per-record revision field).
  - incoming batch_revision > stored batch_revision → update record.
  - incoming batch_revision == stored batch_revision → unchanged (no-op).
  - incoming batch_revision < stored batch_revision → skipped_older.
  - Same-revision content difference → log a warning, do NOT apply.

Turn numbers (Phase 0.5):
  - Meeting turns have NO explicit index field.
  - Use 1-based array position for display.

Identity: (source_type, source_id) everywhere.
"""

import json
import re
import datetime
import random
from pathlib import Path
from typing import Optional

import pytz

from app.db import get_conn, init_db, get_record, get_transcript

IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Transcript intake state logic
# ---------------------------------------------------------------------------

def _classify_transcript_status(source_type: str, record: dict, tp: dict) -> tuple[str, bool]:
    """
    Returns (transcript_status, has_usable_transcript).

    Statuses:
      transcript_usable          — turns exist and text is non-empty, OR payload.transcript is non-empty for calls
      transcript_pending         — no turns yet, but reason says 'later'
      recorded_but_no_usable_text — recording exists but no usable speech
      no_recording               — no recording at all
      call_no_transcript         — call without any transcript text
    """
    payload = record.get("payload") or {}

    if source_type == "call":
        # Check transcript_payload.turns first
        turns = (tp or {}).get("turns", [])
        has_turns_text = any((t.get("text") or "").strip() for t in turns)
        # Also check payload.transcript flat string (C01-C10 style)
        flat_transcript = (payload.get("transcript") or "").strip()
        if has_turns_text or flat_transcript:
            return "transcript_usable", True
        return "call_no_transcript", False

    # meeting
    turns = (tp or {}).get("turns", [])
    reason = ((tp or {}).get("unavailable_reason") or "").strip()
    meeting_status = payload.get("notetaker_status", "")
    summary_status = payload.get("summary_status", "")

    has_text = any((t.get("text") or "").strip() for t in turns)
    if has_text:
        return "transcript_usable", True

    if reason and "later" in reason.lower():
        return "transcript_pending", False

    # recorded but no usable speech: notetaker was there but nothing usable
    if meeting_status in ("succeeded", "failed") or summary_status == "failed":
        return "recorded_but_no_usable_text", False

    # no recording / notetaker never set up / cancelled
    if meeting_status in ("cancelled", "not_scheduled") or summary_status is None:
        return "no_recording", False

    return "no_recording", False



def _build_turns_json(source_type: str, tp: dict) -> Optional[str]:
    """Serialize turns (with 1-based position as turn_number for meetings)."""
    turns = (tp or {}).get("turns", [])
    if not turns:
        return None
    result = []
    for i, t in enumerate(turns, 1):
        entry = dict(t)
        entry["turn_number"] = i  # always 1-based array position
        result.append(entry)
    return json.dumps(result, ensure_ascii=False)


def _local_date_ist(record: dict) -> str:
    """Return the IST date string for a record, falling back to 2026-08-21."""
    payload = record.get("payload") or {}
    for field in ("start_time", "created_at", "date", "call_date"):
        raw = payload.get(field)
        if raw:
            try:
                dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt.astimezone(IST).strftime("%Y-%m-%d")
            except Exception:
                pass
    return "2026-08-21"


# ---------------------------------------------------------------------------
# Data-quality flag detection
# ---------------------------------------------------------------------------

def _detect_dq_flags(source_type: str, source_id: str, record: dict) -> list[dict]:
    flags = []
    p = record.get("payload") or {}

    if source_type == "call":
        # B13: talk_time > duration
        talk = p.get("talk_time_seconds")
        dur = p.get("duration_seconds")
        if talk is not None and dur is not None and talk > dur:
            flags.append({
                "flag_key": "talk_time_exceeds_duration",
                "description": f"talk_time_seconds ({talk}s) > duration_seconds ({dur}s). "
                               f"Possible timer/overlap measurement issue."
            })
        # B02/B06/B08/B11: prior_connects_ever inconsistency
        prior = p.get("prior_connects_ever")
        first_ever = p.get("first_connect_ever")
        if prior is not None and first_ever is True and prior > 0:
            flags.append({
                "flag_key": "prior_connects_inconsistency",
                "description": f"first_connect_ever=true but prior_connects_ever={prior} (should be 0). "
                               f"Inconsistency in source data."
            })
        # null rep_user_id
        if p.get("rep_user_id") is None and p.get("rep_email"):
            flags.append({
                "flag_key": "null_rep_user_id",
                "description": f"rep_user_id is null; rep identified by email ({p.get('rep_email')}) for display only."
            })

    if source_type == "meeting":
        # M10/M14: attendee_count potentially misleading
        ac = p.get("attendee_count")
        attendees = p.get("attendees") or []
        if ac is not None and len(attendees) > 0 and ac != len(attendees):
            flags.append({
                "flag_key": "attendee_count_mismatch",
                "description": f"attendee_count={ac} but attendees array has {len(attendees)} entries. "
                               f"Count may include external/uninvited participants."
            })

    return flags


# ---------------------------------------------------------------------------
# Core import function
# ---------------------------------------------------------------------------

def import_batch(batch_file: str, shuffle: bool = False, db_path=None) -> dict:
    """
    Import a batch JSON file into the database.
    Returns an import-log dict.
    """
    init_db(db_path)
    path = Path(batch_file)
    with open(path, encoding="utf-8") as f:
        batch = json.load(f)

    batch_revision = batch.get("revision", 0)
    batch_id = batch.get("batch_id", "unknown")
    records = batch.get("records", [])

    if shuffle:
        records = list(records)
        random.shuffle(records)

    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()

    log = {
        "batch_id": batch_id,
        "batch_revision": batch_revision,
        "batch_file": str(path),
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_older": 0,
        "warnings": [],
    }

    with get_conn(db_path) as conn:
        for record in records:
            source_type = record["source_type"]
            source_id = record["source_id"]
            record_ref = record.get("record_ref", "")
            tp = record.get("transcript_payload") or {}

            existing = get_record(conn, source_type, source_id)

            if existing:
                stored_rev = existing["batch_revision"]
                if batch_revision < stored_rev:
                    log["skipped_older"] += 1
                    continue
                elif batch_revision == stored_rev:
                    # Same revision — check for content diff and warn
                    new_payload = json.dumps(record.get("payload") or {}, sort_keys=True)
                    old_payload = json.dumps(
                        json.loads(existing["payload_json"]).get("payload") or {},
                        sort_keys=True
                    )
                    if new_payload != old_payload:
                        log["warnings"].append(
                            f"SAME-REVISION CONTENT DIFF for ({source_type},{source_id}) "
                            f"rev={batch_revision}: payload differs — NOT applied."
                        )
                    log["unchanged"] += 1
                    continue
                else:
                    # Higher revision — update
                    action = "update"
            else:
                action = "insert"

            transcript_status, has_usable = _classify_transcript_status(source_type, record, tp)
            turns_json = _build_turns_json(source_type, tp)
            transcript_text = None
            if tp.get("turns"):
                transcript_text = "\n".join(
                    (t.get("text") or "").strip() for t in tp["turns"]
                    if (t.get("text") or "").strip()
                )
            elif (record.get("payload") or {}).get("transcript"):
                transcript_text = (record.get("payload") or {}).get("transcript").strip()
            unavailable_reason = tp.get("unavailable_reason")
            local_date = _local_date_ist(record)

            full_payload_json = json.dumps(record, ensure_ascii=False)

            if action == "insert":
                conn.execute("""
                    INSERT INTO source_record
                    (source_type, source_id, record_ref, batch_revision,
                     payload_json, transcript_status, has_usable_transcript,
                     local_date_ist, imported_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (source_type, source_id, record_ref, batch_revision,
                      full_payload_json, transcript_status, 1 if has_usable else 0,
                      local_date, now_str))

                # Insert transcript row
                conn.execute("""
                    INSERT INTO transcript
                    (source_type, source_id, transcript_text, turns_json,
                     unavailable_reason, batch_revision, attached_at)
                    VALUES (?,?,?,?,?,?,?)
                """, (source_type, source_id, transcript_text, turns_json,
                      unavailable_reason, batch_revision, now_str))

                # Insert DQ flags
                flags = _detect_dq_flags(source_type, source_id, record)
                for fl in flags:
                    conn.execute("""
                        INSERT OR IGNORE INTO data_quality_flag
                        (source_type, source_id, flag_key, description)
                        VALUES (?,?,?,?)
                    """, (source_type, source_id, fl["flag_key"], fl["description"]))

                log["inserted"] += 1

            else:  # update
                conn.execute("""
                    UPDATE source_record
                    SET record_ref=?, batch_revision=?, payload_json=?,
                        transcript_status=?, has_usable_transcript=?,
                        local_date_ist=?, updated_at=?
                    WHERE source_type=? AND source_id=?
                """, (record_ref, batch_revision, full_payload_json,
                      transcript_status, 1 if has_usable else 0,
                      local_date, now_str,
                      source_type, source_id))

                conn.execute("""
                    INSERT OR REPLACE INTO transcript
                    (source_type, source_id, transcript_text, turns_json,
                     unavailable_reason, batch_revision, attached_at)
                    VALUES (?,?,?,?,?,?,?)
                """, (source_type, source_id, transcript_text, turns_json,
                      unavailable_reason, batch_revision, now_str))

                # Mark analyses as stale
                conn.execute("""
                    UPDATE analysis SET stale=1
                    WHERE source_type=? AND source_id=?
                """, (source_type, source_id))

                # Update review state to needs_review if stale
                conn.execute("""
                    INSERT OR REPLACE INTO review_state (source_type, source_id, state, updated_at)
                    VALUES (?, ?, 'needs_review', ?)
                """, (source_type, source_id, now_str))

                log["updated"] += 1

        # Record the import run
        conn.execute("""
            INSERT INTO import_run
            (batch_id, batch_revision, batch_file, run_at,
             inserted, updated, unchanged, skipped_older, warnings_json)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (batch_id, batch_revision, str(path), now_str,
              log["inserted"], log["updated"], log["unchanged"],
              log["skipped_older"], json.dumps(log["warnings"])))

    return log
