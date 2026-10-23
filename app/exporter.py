"""
app/exporter.py — Export engine.
Writes exports/ folder structure and manifest.json + manifest.csv.
"""
import json
import csv
import datetime
import zipfile
import pytz
from pathlib import Path

from app.db import get_conn

EXPORTS_DIR = Path(__file__).parent.parent / "exports"
IST = pytz.timezone("Asia/Kolkata")


def run_export(db_path=None) -> dict:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORTS_DIR / "by_route").mkdir(exist_ok=True)
    (EXPORTS_DIR / "by_record").mkdir(exist_ok=True)

    now_str = datetime.datetime.now(tz=IST).isoformat()
    manifest_rows = []

    with get_conn(db_path) as conn:
        records = conn.execute(
            "SELECT * FROM source_record ORDER BY source_type, record_ref"
        ).fetchall()

    for rec in records:
        st = rec["source_type"]
        sid = rec["source_id"]
        ref = rec["record_ref"] or f"{st}_{sid[:8]}"
        ts_status = rec["transcript_status"]
        batch_rev = rec["batch_revision"]

        with get_conn(db_path) as conn:
            ra = conn.execute(
                "SELECT * FROM route_assignment WHERE source_type=? AND source_id=?",
                (st, sid)
            ).fetchone()
            analyses = conn.execute(
                "SELECT * FROM analysis WHERE source_type=? AND source_id=?",
                (st, sid)
            ).fetchall()
            rv = conn.execute(
                "SELECT state FROM review_state WHERE source_type=? AND source_id=?",
                (st, sid)
            ).fetchone()
            tr = conn.execute(
                "SELECT batch_revision, turns_json FROM transcript WHERE source_type=? AND source_id=?",
                (st, sid)
            ).fetchone()

        suggested = json.loads(ra["suggested_routes"] if ra and ra["suggested_routes"] else "[]")
        manual = json.loads(ra["manual_routes"] if ra and ra["manual_routes"] else "null") or []
        effective_routes = manual if manual else suggested
        route_origin = "manual" if manual else "suggested"
        manually_corrected = bool(manual)
        review_state = rv["state"] if rv else "not_reviewed"
        analysis_revs = [a["generated_from_revision"] for a in analyses] if analyses else []
        max_analysis_rev = max(analysis_revs) if analysis_revs else None
        stale = any(a["stale"] for a in analyses) if analyses else False

        # By-record index
        rec_dir = EXPORTS_DIR / "by_record" / f"{st}_{sid[:12]}"
        rec_dir.mkdir(parents=True, exist_ok=True)
        output_paths = []

        index_lines = [
            f"# {ref} — {st}",
            f"**source_id**: {sid}",
            f"**transcript_status**: {ts_status}",
            f"**review_state**: {review_state}",
            f"**effective_routes**: {', '.join(effective_routes) or '—'}",
            f"**route_origin**: {route_origin}",
            "",
        ]

        for analysis in analyses:
            route = analysis["route"]
            out_data = json.loads(analysis["output_json"])

            # By-route export
            route_dir = EXPORTS_DIR / "by_route" / route
            route_dir.mkdir(parents=True, exist_ok=True)
            route_filename = f"{st}_{sid[:12]}__{route}"
            route_md = route_dir / f"{route_filename}.md"
            route_json = route_dir / f"{route_filename}.json"

            # Write MD
            md_lines = [
                f"# {ref} — {route}",
                f"**source_type**: {st} | **source_id**: {sid}",
                f"**origin**: {out_data.get('origin', 'pre-generated')}",
                f"**generated_from_revision**: {analysis['generated_from_revision']}",
                f"**stale**: {bool(analysis['stale'])}",
                "",
                "## What happened and why it matters",
                out_data.get("summary", "_No summary._"),
                "",
                "## Evidence",
            ]
            for ev in out_data.get("evidence", []):
                if ev.get("quote"):
                    md_lines.append(f"- **{ev.get('label', '')}**: \"{ev['quote']}\"")
                elif ev.get("turn_number"):
                    md_lines.append(f"- Turn {ev['turn_number']}: {ev.get('label', '')}")
            md_lines += ["", "## What the evidence does NOT establish",
                         out_data.get("not_established", "_Not specified._"),
                         "", "## Next step"]
            ns = out_data.get("next_step", {})
            if isinstance(ns, dict):
                owner = ns.get("owner", "")
                step = ns.get("action", "_Not specified._")
                md_lines.append(f"- {step}" + (f" (Owner: {owner})" if owner else ""))
            else:
                md_lines.append(f"- {ns}")

            route_md.write_text("\n".join(md_lines), encoding="utf-8")
            with open(route_json, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2, ensure_ascii=False)

            output_paths.append(str(route_md))
            index_lines.append(f"- [{route}]({route_md})")

        (rec_dir / "index.md").write_text("\n".join(index_lines), encoding="utf-8")

        manifest_rows.append({
            "source_type": st,
            "source_id": sid,
            "record_ref": ref,
            "routes": json.dumps(effective_routes),
            "route_origin": route_origin,
            "manually_corrected": manually_corrected,
            "output_paths": json.dumps(output_paths),
            "review_state": review_state,
            "transcript_status": ts_status,
            "source_revision": batch_rev,
            "analysis_revision": max_analysis_rev,
            "stale": stale,
            "exported_at": now_str,
        })

    # Write manifest.json
    manifest_json = EXPORTS_DIR / "manifest.json"
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest_rows, f, indent=2, ensure_ascii=False)

    # Write manifest.csv
    manifest_csv = EXPORTS_DIR / "manifest.csv"
    if manifest_rows:
        with open(manifest_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=manifest_rows[0].keys())
            writer.writeheader()
            writer.writerows(manifest_rows)

    # Zip everything
    zip_path = Path(__file__).parent.parent / "exports.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for fp in EXPORTS_DIR.rglob("*"):
            if fp.is_file():
                z.write(fp, fp.relative_to(EXPORTS_DIR.parent))

    return {
        "total": len(manifest_rows),
        "output_dir": str(EXPORTS_DIR),
        "manifest_path": str(manifest_json),
        "zip_path": str(zip_path),
    }
