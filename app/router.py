"""
app/router.py — Rule-based routing engine.

Routes:
  customer_follow_up       — action items, committed follow-ups, open items mentioned in conversation
  deal_next_steps          — deal progression: demos, proposals, negotiations, close language
  sales_coaching           — coaching signals: objection handling, missed questions, positive technique
  support_account_admin    — login/permission issues, billing, account setup, technical support
  internal_vendor_note     — internal training, vendor as buyer, internal process discussions
  needs_human_decision     — ambiguous, conflicting signals, or insufficient transcript

Multi-route allowed.
Every route has: suggested_routes[], reason (plain English), confidence (high/medium/low), triggers[].
"""

import json
import re
from typing import Optional

from app.db import get_conn, get_transcript, get_record


# ---------------------------------------------------------------------------
# Signal patterns (all lowercase for matching)
# ---------------------------------------------------------------------------

FOLLOW_UP_SIGNALS = [
    r"\bfollow[ -]?up\b", r"\bnext step\b", r"\baction item\b",
    r"\bwill send\b", r"\bwill share\b", r"\bwill schedule\b",
    r"\blet me know\b", r"\bcircle back\b", r"\bget back to\b",
    r"\bremind\b", r"\bpending\b", r"\bopen item\b", r"\bfollow through\b",
]

DEAL_SIGNALS = [
    r"\bdemo\b", r"\bproposal\b", r"\bprice\b", r"\bpricin\b",
    r"\bcontract\b", r"\bquote\b", r"\bclose\b", r"\btrial\b",
    r"\bpilot\b", r"\bnegotiat\b", r"\bbudget\b", r"\broi\b",
    r"\bpurchase\b", r"\bbuy\b", r"\bsign\b", r"\bdecision\b",
    r"\bevaluat\b", r"\bcompetitor\b", r"\bcompare\b", r"\bsolution\b",
]

COACHING_SIGNALS = [
    r"\bobjection\b", r"\bhesitant\b", r"\bnot sure\b", r"\bnot ready\b",
    r"\btoo expensive\b", r"\btoo costly\b", r"\bother option\b",
    r"\bwhy should\b", r"\bwhat.*different\b", r"\bwhat.*better\b",
    r"\bbut we\b", r"\bconcern\b", r"\bworried\b",
    r"\bgood question\b", r"\bgreat point\b", r"\bunderstand\b",
    r"\bpush back\b", r"\bpushback\b", r"\bchallenge\b",
]

SUPPORT_SIGNALS = [
    r"\blogin\b", r"\bpassword\b", r"\breset\b", r"\bpermission\b",
    r"\baccess\b", r"\baccount\b", r"\bbilling\b", r"\binvoice\b",
    r"\bsupport ticket\b", r"\bbug\b", r"\berror\b", r"\bbroken\b",
    r"\bnot working\b", r"\bcan't log in\b", r"\bcannot access\b",
    r"\bsetup\b", r"\bconfigure\b", r"\bonboarding\b", r"\bintegration\b",
]

INTERNAL_SIGNALS = [
    r"\binternal\b", r"\btraining\b", r"\bonboard\b", r"\bteam meeting\b",
    r"\bstaff\b", r"\bmanager\b", r"\bprocess\b", r"\bworkflow\b",
    r"\bvendor\b", r"\bsupplier\b", r"\bour team\b", r"\bwe are buying\b",
    r"\bwe need to purchase\b", r"\bspend\b",
]


def _score_text(text: str, patterns: list[str]) -> list[str]:
    """Return list of matching trigger substrings (for evidence display)."""
    text_lower = text.lower()
    hits = []
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text_lower):
            span = text[m.start():m.end()]
            if span not in seen:
                hits.append(span)
                seen.add(span)
    return hits


def _confidence(n_hits: int, total_signals: int) -> str:
    ratio = n_hits / max(len(total_signals), 1)
    if ratio >= 0.15:
        return "high"
    if ratio >= 0.06:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Label conflict detection
# ---------------------------------------------------------------------------

LABEL_CONFLICT_CHECKS = {
    "deal_next_steps": DEAL_SIGNALS,
    "customer_follow_up": FOLLOW_UP_SIGNALS,
    "sales_coaching": COACHING_SIGNALS,
    "support_account_admin": SUPPORT_SIGNALS,
    "internal_vendor_note": INTERNAL_SIGNALS,
}


def _detect_label_conflicts(payload: dict, transcript_text: str) -> list[dict]:
    """
    Detect cases where stored label is inconsistent with transcript content.
    Never overwrites stored label; returns display-only conflict objects.
    """
    conflicts = []
    # Example: call_purpose or meeting_type vs transcript evidence
    stored_type = (
        payload.get("call_type") or
        payload.get("meeting_type") or
        payload.get("call_purpose") or ""
    ).lower()

    if not stored_type or not transcript_text:
        return conflicts

    text = transcript_text.lower()
    for route, patterns in LABEL_CONFLICT_CHECKS.items():
        triggers = _score_text(transcript_text, patterns)
        if triggers and route.replace("_", " ") not in stored_type:
            # Only flag if stored type explicitly contradicts
            pass  # Keep conservative — flag only obvious contradictions

    # C02/C03/C04: if stored label says one thing but transcript signals something else strongly
    if "internal" in stored_type:
        customer_hits = _score_text(transcript_text, DEAL_SIGNALS + FOLLOW_UP_SIGNALS)
        if len(customer_hits) >= 3:
            conflicts.append({
                "stored_label": stored_type,
                "suggested_route": "customer_follow_up or deal_next_steps",
                "trigger_quote": customer_hits[0] if customer_hits else "",
                "note": "Analyst assessment: transcript has customer-facing signals despite internal label."
            })

    return conflicts


# ---------------------------------------------------------------------------
# Main routing function
# ---------------------------------------------------------------------------

def compute_routes(source_type: str, source_id: str, db_path=None) -> dict:
    """
    Compute suggested routes for a single record.
    Returns dict with: suggested_routes, reason, confidence, triggers, conflicts.
    """
    with get_conn(db_path) as conn:
        rec = get_record(conn, source_type, source_id)
        tr = get_transcript(conn, source_type, source_id)

    if not rec:
        return {"suggested_routes": [], "reason": "Record not found.", "confidence": "low", "triggers": [], "conflicts": []}

    payload = json.loads(rec["payload_json"])
    p = payload.get("payload") or {}
    tp = payload.get("transcript_payload") or {}
    transcript_text = (tr["transcript_text"] if tr else None) or ""

    routes = []
    reasons = []
    all_triggers = []
    conflicts = []

    if not transcript_text.strip():
        # No usable transcript — route based on metadata only
        status = rec["transcript_status"]
        if status in ("recorded_but_no_usable_text", "no_recording", "call_no_transcript"):
            routes.append("needs_human_decision")
            reasons.append(f"No usable transcript ({status}); cannot determine routing from content.")
        elif status == "transcript_pending":
            routes.append("needs_human_decision")
            reasons.append("Transcript pending late delivery; re-route after transcript is available.")
        return {
            "suggested_routes": routes,
            "reason": " ".join(reasons) or "No transcript available.",
            "confidence": "low",
            "triggers": [],
            "conflicts": [],
        }

    # Score transcript against each route's signals
    follow_hits = _score_text(transcript_text, FOLLOW_UP_SIGNALS)
    deal_hits = _score_text(transcript_text, DEAL_SIGNALS)
    coach_hits = _score_text(transcript_text, COACHING_SIGNALS)
    support_hits = _score_text(transcript_text, SUPPORT_SIGNALS)
    internal_hits = _score_text(transcript_text, INTERNAL_SIGNALS)

    thresholds = {"follow": 2, "deal": 2, "coach": 2, "support": 2, "internal": 2}

    if len(follow_hits) >= thresholds["follow"]:
        routes.append("customer_follow_up")
        reasons.append(f"Follow-up signals detected ({len(follow_hits)} hits).")
        all_triggers.extend(follow_hits[:3])

    if len(deal_hits) >= thresholds["deal"]:
        routes.append("deal_next_steps")
        reasons.append(f"Deal progression signals detected ({len(deal_hits)} hits).")
        all_triggers.extend(deal_hits[:3])

    if len(coach_hits) >= thresholds["coach"]:
        routes.append("sales_coaching")
        reasons.append(f"Coaching signals detected ({len(coach_hits)} hits: objections/technique).")
        all_triggers.extend(coach_hits[:3])

    if len(support_hits) >= thresholds["support"]:
        routes.append("support_account_admin")
        reasons.append(f"Support/admin signals detected ({len(support_hits)} hits).")
        all_triggers.extend(support_hits[:3])

    if len(internal_hits) >= thresholds["internal"] and source_type == "meeting":
        routes.append("internal_vendor_note")
        reasons.append(f"Internal/vendor signals detected ({len(internal_hits)} hits).")
        all_triggers.extend(internal_hits[:3])

    if not routes:
        routes.append("needs_human_decision")
        reasons.append("Insufficient signals for automatic routing; human review recommended.")

    conflicts = _detect_label_conflicts(p, transcript_text)

    # Overall confidence
    max_hits = max(len(follow_hits), len(deal_hits), len(coach_hits), len(support_hits), len(internal_hits))
    conf = _confidence(max_hits, FOLLOW_UP_SIGNALS + DEAL_SIGNALS)

    return {
        "suggested_routes": list(dict.fromkeys(routes)),  # dedupe order-preserving
        "reason": " ".join(reasons),
        "confidence": conf,
        "triggers": list(dict.fromkeys(all_triggers))[:6],
        "conflicts": conflicts,
    }


def route_all(db_path=None):
    """Run routing for all records with usable transcripts and store results."""
    from app.db import get_conn, init_db
    import datetime, pytz
    init_db(db_path)

    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT source_type, source_id FROM source_record"
        ).fetchall()

    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()

    for row in rows:
        st, sid = row["source_type"], row["source_id"]
        result = compute_routes(st, sid, db_path)

        with get_conn(db_path) as conn:
            existing = conn.execute(
                "SELECT manual_routes, manual_set_at, manual_set_by, manual_reason, manual_previous "
                "FROM route_assignment WHERE source_type=? AND source_id=?",
                (st, sid)
            ).fetchone()
            manual_routes = existing["manual_routes"] if existing else None

            conn.execute("""
                INSERT OR REPLACE INTO route_assignment
                (source_type, source_id, suggested_routes, suggested_reason,
                 suggested_confidence, suggested_triggers, manual_routes,
                 manual_set_at, manual_set_by, manual_reason, manual_previous)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                st, sid,
                json.dumps(result["suggested_routes"]),
                result["reason"],
                result["confidence"],
                json.dumps(result["triggers"]),
                manual_routes,
                existing["manual_set_at"] if existing else None,
                existing["manual_set_by"] if existing else None,
                existing["manual_reason"] if existing else None,
                existing["manual_previous"] if existing else None,
            ))

    return len(rows)
