"""
app/quote_validator.py — Exact-quote validator.

For calls: every cited quote MUST be a verbatim substring
(whitespace-normalised) of the stored transcript.

For meetings: turn references use 1-based array position.
"""
import re
import json
from app.db import get_conn, get_transcript


def _normalise(text: str) -> str:
    """Collapse runs of whitespace to a single space, strip."""
    return re.sub(r"\s+", " ", text).strip()


def validate_call_quote(source_type: str, source_id: str, quote: str, db_path=None) -> dict:
    """
    Returns {valid: bool, reason: str}.
    For meetings, validates that the turn_number is within range.
    """
    if source_type != "call":
        return {"valid": True, "reason": "Quote validation applies to calls only."}

    with get_conn(db_path) as conn:
        tr = get_transcript(conn, source_type, source_id)

    if not tr or not tr["transcript_text"]:
        return {"valid": False, "reason": "No transcript available to validate against."}

    full_text = _normalise(tr["transcript_text"])
    norm_quote = _normalise(quote)

    if norm_quote in full_text:
        return {"valid": True, "reason": "Quote verified as verbatim substring."}

    # Try partial match for slight whitespace difference
    return {"valid": False, "reason": f"Quote NOT found verbatim in transcript. First 60 chars: '{norm_quote[:60]}'"}


def validate_meeting_turn(source_type: str, source_id: str, turn_number: int, db_path=None) -> dict:
    """Check that turn_number (1-based) is within bounds of stored turns."""
    with get_conn(db_path) as conn:
        tr = get_transcript(conn, source_type, source_id)

    if not tr or not tr["turns_json"]:
        return {"valid": False, "reason": "No turns stored."}

    turns = json.loads(tr["turns_json"])
    if 1 <= turn_number <= len(turns):
        turn = turns[turn_number - 1]
        return {"valid": True, "reason": f"Turn {turn_number} exists.", "turn": turn}
    return {"valid": False, "reason": f"Turn {turn_number} out of range (1–{len(turns)})."}


def validate_analyses_all(analyses_json_path: str, db_path=None) -> list[dict]:
    """
    Read a pre-generated analysis JSON file and validate all cited quotes/turns.
    Returns list of validation results.
    """
    import json
    from pathlib import Path

    path = Path(analyses_json_path)
    if not path.exists():
        return [{"error": f"File not found: {analyses_json_path}"}]

    with open(path, encoding="utf-8") as f:
        analyses = json.load(f)

    results = []
    for entry in analyses:
        st = entry.get("source_type")
        sid = entry.get("source_id")
        for evidence in entry.get("evidence", []):
            quote = evidence.get("quote")
            turn_num = evidence.get("turn_number")
            if st == "call" and quote:
                r = validate_call_quote(st, sid, quote, db_path)
                results.append({"source_type": st, "source_id": sid, "quote": quote[:40], **r})
            elif st == "meeting" and turn_num:
                r = validate_meeting_turn(st, sid, turn_num, db_path)
                results.append({"source_type": st, "source_id": sid, "turn_number": turn_num, **r})
    return results
