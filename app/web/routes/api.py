"""
app/web/routes/api.py — JSON API endpoints for UI actions.
"""
import json
import datetime
import pytz
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List

from app.db import get_conn, get_record
from app.router import route_all
from app.importer import import_batch
from app.exporter import run_export
from app.db import reset_db, init_db

router = APIRouter(prefix="/api")


class RouteCorrection(BaseModel):
    source_type: str
    source_id: str
    manual_routes: List[str]
    manual_reason: Optional[str] = ""


@router.post("/route/correct")
async def correct_route(body: RouteCorrection):
    """Manager manually corrects route assignment."""
    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()
    with get_conn() as conn:
        rec = get_record(conn, body.source_type, body.source_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Record not found")

        existing = conn.execute(
            "SELECT * FROM route_assignment WHERE source_type=? AND source_id=?",
            (body.source_type, body.source_id)
        ).fetchone()

        prev = json.loads(existing["manual_routes"] if existing and existing["manual_routes"] else "null") or []

        conn.execute("""
            INSERT OR REPLACE INTO route_assignment
            (source_type, source_id, suggested_routes, suggested_reason,
             suggested_confidence, suggested_triggers, manual_routes,
             manual_set_at, manual_set_by, manual_reason, manual_previous)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            body.source_type, body.source_id,
            existing["suggested_routes"] if existing else "[]",
            existing["suggested_reason"] if existing else "",
            existing["suggested_confidence"] if existing else "low",
            existing["suggested_triggers"] if existing else "[]",
            json.dumps(body.manual_routes),
            now_str,
            "manager",
            body.manual_reason,
            json.dumps(prev),
        ))

        conn.execute("""
            INSERT OR REPLACE INTO review_state (source_type, source_id, state, updated_at)
            VALUES (?, ?, 'reviewed', ?)
        """, (body.source_type, body.source_id, now_str))

    return {"status": "ok", "manual_routes": body.manual_routes}


@router.post("/route/reset")
async def reset_manual_route(source_type: str, source_id: str):
    """Remove manual route override — falls back to suggested."""
    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()
    with get_conn() as conn:
        conn.execute("""
            UPDATE route_assignment SET manual_routes=NULL, manual_set_at=NULL,
            manual_reason=NULL WHERE source_type=? AND source_id=?
        """, (source_type, source_id))
        conn.execute("""
            INSERT OR REPLACE INTO review_state (source_type, source_id, state, updated_at)
            VALUES (?, ?, 'not_reviewed', ?)
        """, (source_type, source_id, now_str))
    return {"status": "ok"}


@router.post("/import")
async def api_import(batch_file: str, shuffle: bool = False):
    """Trigger import via API."""
    try:
        log = import_batch(batch_file, shuffle=shuffle)
        return log
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def api_export():
    """Trigger export via API."""
    try:
        result = run_export()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def api_reset():
    """Reset database."""
    reset_db()
    return {"status": "reset complete"}


@router.get("/stats")
async def api_stats():
    """Quick stats for the UI."""
    from app.db import count_records, count_usable_transcripts
    with get_conn() as conn:
        total = count_records(conn)
        usable = count_usable_transcripts(conn)
        calls = conn.execute("SELECT COUNT(*) FROM source_record WHERE source_type='call'").fetchone()[0]
        meetings = conn.execute("SELECT COUNT(*) FROM source_record WHERE source_type='meeting'").fetchone()[0]
    return {"total": total, "usable": usable, "calls": calls, "meetings": meetings}


@router.get("/definitions")
async def api_definitions():
    """Return metric definitions for popover display."""
    return {
        "total_records": {
            "numerator": "All records in database",
            "denominator": "44 (30 calls + 14 meetings in original delivery)",
            "period": "21 Aug 2026 (Asia/Kolkata)",
            "missing_data_effect": "Count stays 44 after update (M07 late transcript attaches, does not add a record)",
        },
        "usable_transcripts": {
            "numerator": "Records where transcript_status = transcript_usable",
            "denominator": "44 total records",
            "period": "21 Aug 2026 (Asia/Kolkata)",
            "missing_data_effect": "17/44 before update batch; 18/44 after (M07 transcript arrives late)",
        },
        "usable_calls": {
            "numerator": "Calls with at least one non-empty turn in transcript_payload",
            "denominator": "30 calls",
            "period": "21 Aug 2026 (Asia/Kolkata)",
            "missing_data_effect": "20 calls have no usable transcript text",
        },
        "usable_meetings": {
            "numerator": "Meetings with at least one non-empty turn in transcript_payload",
            "denominator": "14 meetings",
            "period": "21 Aug 2026 (Asia/Kolkata)",
            "missing_data_effect": "6 meetings have no usable transcript (recording issues / not scheduled)",
        },
        "duration_seconds": {
            "unit": "seconds (converted to minutes:seconds in UI)",
            "note": "talk_time_seconds ≠ duration_seconds; talk time is active speech only",
        },
    }
