"""
app/web/routes/dashboard.py — Manager Dashboard (GET /)
"""
import json
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from app.web.common import templates
from app.db import get_conn

router = APIRouter()


def _build_dashboard_data(
    source_type_filter=None, rep_email_filter=None, route_filter=None
):
    """Aggregate dashboard metrics with filter awareness."""
    with get_conn() as conn:
        all_records = conn.execute("SELECT * FROM source_record").fetchall()
        all_ra = {
            (r["source_type"], r["source_id"]): r
            for r in conn.execute("SELECT * FROM route_assignment").fetchall()
        }
        all_rv = {
            (r["source_type"], r["source_id"]): r["state"]
            for r in conn.execute("SELECT * FROM review_state").fetchall()
        }
        all_analyses = conn.execute("SELECT * FROM analysis").fetchall()
        dq_flags = conn.execute("SELECT * FROM data_quality_flag").fetchall()
        import_runs = conn.execute("SELECT * FROM import_run ORDER BY id DESC LIMIT 5").fetchall()

    # Build person lists
    call_reps = {}
    meeting_organisers = {}
    for rec in all_records:
        p = json.loads(rec["payload_json"])
        payload = p.get("payload") or {}
        if rec["source_type"] == "call":
            email = payload.get("rep_email", "")
            name = payload.get("rep_name", email or "Unknown Rep")
            if email:
                call_reps[email] = name
        else:
            email = payload.get("organizer_email", "")
            name = payload.get("organizer_name", email or "Unknown Organiser")
            if email:
                meeting_organisers[email] = name

    # Apply filters
    filtered = []
    for rec in all_records:
        p = json.loads(rec["payload_json"])
        payload = p.get("payload") or {}

        if source_type_filter and rec["source_type"] != source_type_filter:
            continue

        if rep_email_filter:
            if payload.get("rep_email") != rep_email_filter:
                continue

        if route_filter:
            key = (rec["source_type"], rec["source_id"])
            ra = all_ra.get(key)
            suggested = json.loads(ra["suggested_routes"] if ra and ra["suggested_routes"] else "[]")
            manual = json.loads(ra["manual_routes"] if ra and ra["manual_routes"] else "null") or []
            effective = manual if manual else suggested
            if route_filter not in effective:
                continue

        filtered.append(rec)

    total = len(filtered)
    calls = sum(1 for r in filtered if r["source_type"] == "call")
    meetings = sum(1 for r in filtered if r["source_type"] == "meeting")
    usable = sum(1 for r in filtered if r["has_usable_transcript"])

    # Calls breakdown
    usable_calls = sum(1 for r in filtered if r["source_type"] == "call" and r["has_usable_transcript"])
    usable_meetings = sum(1 for r in filtered if r["source_type"] == "meeting" and r["has_usable_transcript"])

    # Transcript status breakdown
    status_counts = {}
    for r in filtered:
        s = r["transcript_status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    # Route counts
    route_counts = {}
    for rec in filtered:
        key = (rec["source_type"], rec["source_id"])
        ra = all_ra.get(key)
        suggested = json.loads(ra["suggested_routes"] if ra and ra["suggested_routes"] else "[]")
        manual = json.loads(ra["manual_routes"] if ra and ra["manual_routes"] else "null") or []
        effective = manual if manual else suggested
        for route in effective:
            route_counts[route] = route_counts.get(route, 0) + 1

    # Stale analyses
    stale_analysis_keys = set()
    for a in all_analyses:
        if a["stale"]:
            stale_analysis_keys.add((a["source_type"], a["source_id"]))

    stale_count = sum(
        1 for r in filtered
        if (r["source_type"], r["source_id"]) in stale_analysis_keys
    )

    # Review states
    needs_review = sum(
        1 for r in filtered
        if all_rv.get((r["source_type"], r["source_id"])) == "needs_review"
    )

    # DQ flag count
    dq_affected = len(set((f["source_type"], f["source_id"]) for f in dq_flags))

    # Label conflicts — count records with non-empty conflicts in route_assignment
    # (stored in suggested_reason containing 'Analyst assessment:')
    label_conflicts = sum(
        1 for ra in all_ra.values()
        if ra and (ra["suggested_reason"] or "").find("conflict") != -1
    )

    return {
        "total": total,
        "calls": calls,
        "meetings": meetings,
        "usable": usable,
        "usable_calls": usable_calls,
        "usable_meetings": usable_meetings,
        "status_counts": status_counts,
        "route_counts": route_counts,
        "stale_count": stale_count,
        "needs_review": needs_review,
        "dq_affected": dq_affected,
        "label_conflicts": label_conflicts,
        "call_reps": call_reps,
        "meeting_organisers": meeting_organisers,
        "import_runs": [dict(r) for r in import_runs],
        "date_label": "21 Aug 2026 (Asia/Kolkata)",
        "filters": {
            "source_type": source_type_filter,
            "rep_email": rep_email_filter,
            "route": route_filter,
        }
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    source_type: str = Query(None),
    rep_email: str = Query(None),
    route: str = Query(None),
):
    try:
        data = _build_dashboard_data(source_type, rep_email, route)
    except Exception as e:
        # Attempt self-healing initialization and retry
        try:
            from app.db import ensure_db_initialized
            ensure_db_initialized()
            data = _build_dashboard_data(source_type, rep_email, route)
        except Exception as retry_err:
            data = {"error": str(retry_err)}
    return templates.TemplateResponse("dashboard.html", {"request": request, **data})
