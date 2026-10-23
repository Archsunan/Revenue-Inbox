"""
app/web/routes/record_detail.py — Single record detail page
"""
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.web.common import templates
from app.db import get_conn, get_record, get_transcript, get_analyses, get_route_assignment, get_review_state, get_data_quality_flags

router = APIRouter()


@router.get("/record/{source_type}/{source_id}", response_class=HTMLResponse)
async def record_detail(request: Request, source_type: str, source_id: str):
    with get_conn() as conn:
        rec = get_record(conn, source_type, source_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Record not found")
        tr = get_transcript(conn, source_type, source_id)
        analyses = get_analyses(conn, source_type, source_id)
        ra = get_route_assignment(conn, source_type, source_id)
        rv = get_review_state(conn, source_type, source_id)
        dq_flags = get_data_quality_flags(conn, source_type, source_id)
        import_runs = conn.execute(
            "SELECT * FROM import_run ORDER BY id DESC LIMIT 10"
        ).fetchall()

    payload = json.loads(rec["payload_json"])
    p = payload.get("payload") or {}
    tp = payload.get("transcript_payload") or {}

    turns = json.loads(tr["turns_json"]) if (tr and tr["turns_json"]) else []

    suggested = json.loads(ra["suggested_routes"] if ra and ra["suggested_routes"] else "[]")
    manual = json.loads(ra["manual_routes"] if ra and ra["manual_routes"] else "null") or []
    effective = manual if manual else suggested

    analyses_out = []
    for a in analyses:
        a_data = json.loads(a["output_json"])
        analyses_out.append({
            "route": a["route"],
            "origin": a["origin"],
            "generated_from_revision": a["generated_from_revision"],
            "stale": bool(a["stale"]),
            "summary": a_data.get("summary", ""),
            "evidence": a_data.get("evidence", []),
            "not_established": a_data.get("not_established", ""),
            "next_step": a_data.get("next_step", {}),
        })

    # Duration
    dur = p.get("duration_seconds") or p.get("meeting_duration_seconds")
    dur_str = f"{int(dur)//60}m {int(dur)%60}s" if dur else "—"

    # Talk time
    talk = p.get("talk_time_seconds")
    talk_str = f"{int(talk)//60}m {int(talk)%60}s" if talk else "—"

    return templates.TemplateResponse("record_detail.html", {
        "request": request,
        "rec": dict(rec),
        "payload": p,
        "tp": tp,
        "turns": turns,
        "tr": dict(tr) if tr else None,
        "analyses": analyses_out,
        "suggested_routes": suggested,
        "manual_routes": manual,
        "effective_routes": effective,
        "route_origin": "manual" if manual else "suggested",
        "ra": dict(ra) if ra else None,
        "review_state": rv["state"] if rv else "not_reviewed",
        "dq_flags": [dict(f) for f in dq_flags],
        "dur_str": dur_str,
        "talk_str": talk_str,
        "raw_json": json.dumps(payload, indent=2, ensure_ascii=False),
        "source_type": source_type,
        "source_id": source_id,
    })


@router.get("/brief", response_class=HTMLResponse)
async def manager_brief(request: Request):
    """Manager brief page — fixed for 21 Aug 2026."""
    with get_conn() as conn:
        usable_recs = conn.execute(
            "SELECT * FROM source_record WHERE has_usable_transcript=1 ORDER BY source_type, record_ref"
        ).fetchall()
        all_analyses = {
            (a["source_type"], a["source_id"]): [dict(a2) for a2 in
                conn.execute("SELECT * FROM analysis WHERE source_type=? AND source_id=?",
                             (a["source_type"], a["source_id"])).fetchall()]
            for a in usable_recs
        }

    brief_items = []
    for rec in usable_recs:
        p = json.loads(rec["payload_json"])
        payload = p.get("payload") or {}
        analyses = all_analyses.get((rec["source_type"], rec["source_id"]), [])
        analyses_data = []
        for a in analyses:
            a_data = json.loads(a["output_json"])
            analyses_data.append({
                "route": a["route"],
                "summary": a_data.get("summary", ""),
                "evidence": a_data.get("evidence", []),
                "next_step": a_data.get("next_step", {}),
            })
        brief_items.append({
            "record_ref": rec["record_ref"],
            "source_type": rec["source_type"],
            "source_id": rec["source_id"],
            "rep_name": payload.get("rep_name") or payload.get("organizer_name") or "—",
            "title": payload.get("title") or payload.get("call_type") or rec["source_type"],
            "transcript_status": rec["transcript_status"],
            "analyses": analyses_data,
        })

    return templates.TemplateResponse("brief.html", {
        "request": request,
        "brief_items": brief_items,
        "date_label": "21 Aug 2026 (Asia/Kolkata)",
        "total_usable": len(usable_recs),
    })
