"""
app/web/routes/records.py — Record list (inbox view)
"""
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from app.web.common import templates
from app.db import get_conn, get_all_records

router = APIRouter()


@router.get("/records", response_class=HTMLResponse)
async def records_view(
    request: Request,
    source_type: str = Query(None),
    rep_email: str = Query(None),
    route: str = Query(None),
    review_state: str = Query(None),
    transcript_status: str = Query(None),
):
    with get_conn() as conn:
        rows = get_all_records(
            conn,
            source_type=source_type,
            rep_email=rep_email,
            route=route,
            review_state_filter=review_state,
            transcript_status=transcript_status,
        )
        all_ra = {
            (r["source_type"], r["source_id"]): r
            for r in conn.execute("SELECT * FROM route_assignment").fetchall()
        }
        dq_flags_raw = conn.execute("SELECT * FROM data_quality_flag").fetchall()
        dq_map = {}
        for f in dq_flags_raw:
            key = (f["source_type"], f["source_id"])
            dq_map.setdefault(key, []).append(f["flag_key"])

    records_out = []
    for rec in rows:
        p = json.loads(rec["payload_json"])
        payload = p.get("payload") or {}
        tp = p.get("transcript_payload") or {}
        key = (rec["source_type"], rec["source_id"])
        ra = all_ra.get(key)
        suggested = json.loads(ra["suggested_routes"] if ra and ra["suggested_routes"] else "[]")
        manual = json.loads(ra["manual_routes"] if ra and ra["manual_routes"] else "null") or []
        effective = manual if manual else suggested

        # Duration formatting
        dur = payload.get("duration_seconds") or payload.get("meeting_duration_seconds")
        dur_str = f"{int(dur)//60}m {int(dur)%60}s" if dur else "—"

        records_out.append({
            "source_type": rec["source_type"],
            "source_id": rec["source_id"],
            "record_ref": rec["record_ref"] or "—",
            "transcript_status": rec["transcript_status"],
            "review_state": rec["review_state"] or "not_reviewed",
            "batch_revision": rec["batch_revision"],
            "local_date_ist": rec["local_date_ist"],
            "rep_email": payload.get("rep_email") or payload.get("organizer_email") or "—",
            "rep_name": payload.get("rep_name") or payload.get("organizer_name") or "—",
            "duration_str": dur_str,
            "effective_routes": effective,
            "suggested_routes": suggested,
            "manual_routes": manual,
            "route_origin": "manual" if manual else "suggested",
            "dq_flags": dq_map.get(key, []),
            "title": payload.get("title") or payload.get("call_type") or rec["source_type"],
        })

    # Build filter options
    with get_conn() as conn:
        all_recs = conn.execute("SELECT payload_json, source_type FROM source_record").fetchall()
    call_reps = {}
    meeting_organisers = {}
    for r in all_recs:
        p = json.loads(r["payload_json"])
        payload = p.get("payload") or {}
        if r["source_type"] == "call":
            email = payload.get("rep_email", "")
            name = payload.get("rep_name", email or "Unknown")
            if email:
                call_reps[email] = name
        else:
            email = payload.get("organizer_email", "")
            name = payload.get("organizer_name", email or "Unknown")
            if email:
                meeting_organisers[email] = name

    return templates.TemplateResponse("records.html", {
        "request": request,
        "records": records_out,
        "total": len(records_out),
        "call_reps": call_reps,
        "meeting_organisers": meeting_organisers,
        "filters": {
            "source_type": source_type,
            "rep_email": rep_email,
            "route": route,
            "review_state": review_state,
            "transcript_status": transcript_status,
        }
    })
