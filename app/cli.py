"""
app/cli.py — Command-line interface.

Commands:
  reset              — wipe DB and re-create schema
  import <file>      — import a batch file [--shuffle]
  demo-load          — reset + import 01_initial.json + 02_update.json + route all
  export             — write exports/ folder and manifest
  serve              — start the FastAPI dev server
"""
import sys
import json
from pathlib import Path


def main():
    args = sys.argv[1:]
    if not args:
        _usage()
        return

    cmd = args[0]

    if cmd == "reset":
        _cmd_reset()
    elif cmd == "import":
        _cmd_import(args[1:])
    elif cmd == "demo-load":
        _cmd_demo_load()
    elif cmd == "export":
        _cmd_export()
    elif cmd == "serve":
        _cmd_serve()
    else:
        print(f"Unknown command: {cmd}")
        _usage()


def _usage():
    print("""
Revenue Intelligence Inbox CLI
Usage:
  python -m app reset
  python -m app import <file.json> [--shuffle]
  python -m app demo-load
  python -m app export
  python -m app serve [--host HOST] [--port PORT]
""")


def _cmd_reset():
    from app.db import reset_db
    reset_db()
    print("Database reset complete.")


def _cmd_import(args):
    from app.importer import import_batch
    if not args:
        print("Error: import requires a file path.")
        return
    file_path = args[0]
    shuffle = "--shuffle" in args
    log = import_batch(file_path, shuffle=shuffle)
    print(f"\n=== Import Log ===")
    print(f"Batch: {log['batch_id']} (rev={log['batch_revision']})")
    print(f"  Inserted:      {log['inserted']}")
    print(f"  Updated:       {log['updated']}")
    print(f"  Unchanged:     {log['unchanged']}")
    print(f"  Skipped-older: {log['skipped_older']}")
    if log["warnings"]:
        print(f"  Warnings ({len(log['warnings'])}):")
        for w in log["warnings"]:
            print(f"    ⚠ {w}")
    else:
        print("  Warnings: none")


def _cmd_demo_load():
    from app.db import reset_db
    from app.importer import import_batch
    from app.router import route_all

    base = Path(__file__).parent.parent / "data"
    reset_db()
    print("DB reset.")

    print("\n--- Importing 01_initial.json ---")
    log1 = import_batch(str(base / "01_initial.json"))
    _print_log(log1)

    print("\n--- Importing 02_update.json ---")
    log2 = import_batch(str(base / "02_update.json"))
    _print_log(log2)

    print("\n--- Running router on all records ---")
    n = route_all()
    print(f"  Routed {n} records.")

    print("\n--- Loading pre-generated analyses ---")
    _load_analyses()

    print("\n--- Summary ---")
    from app.db import get_conn, count_records, count_usable_transcripts
    with get_conn() as conn:
        total = count_records(conn)
        usable = count_usable_transcripts(conn)
    print(f"  Total records:           {total}")
    print(f"  Usable transcripts:      {usable}")
    print(f"  Coverage:                {usable}/{total}")
    print("\nDemo load complete. Run: python -m app serve")


def _load_analyses():
    """Load pre-generated analysis JSON files into DB if they exist."""
    import datetime, pytz
    from app.db import get_conn
    analysis_dir = Path(__file__).parent.parent / "analysis"
    now_str = datetime.datetime.now(tz=pytz.utc).isoformat()
    loaded = 0
    if analysis_dir.exists():
        for fp in analysis_dir.glob("*.json"):
            try:
                with open(fp, encoding="utf-8") as f:
                    entries = json.load(f)
                if not isinstance(entries, list):
                    entries = [entries]
                with get_conn() as conn:
                    for entry in entries:
                        st = entry.get("source_type")
                        sid = entry.get("source_id")
                        route = entry.get("route")
                        rev = entry.get("generated_from_revision", 1)
                        if st and sid and route:
                            conn.execute("""
                                INSERT OR REPLACE INTO analysis
                                (source_type, source_id, route, output_json, origin,
                                 generated_from_revision, stale, created_at)
                                VALUES (?,?,?,?,?,?,?,?)
                            """, (st, sid, route, json.dumps(entry), "pre-generated",
                                  rev, 0, now_str))
                            loaded += 1
            except Exception as e:
                print(f"  Warning: could not load {fp.name}: {e}")
    print(f"  Analyses loaded: {loaded}")


def _cmd_export():
    from app.exporter import run_export
    result = run_export()
    print(f"\n=== Export Complete ===")
    print(f"  Records exported: {result['total']}")
    print(f"  Output dir:       {result['output_dir']}")
    print(f"  Manifest:         {result['manifest_path']}")


def _cmd_serve(host="127.0.0.1", port=8000):
    import uvicorn
    # Parse host/port from sys.argv if provided
    args = sys.argv[2:]
    if "--host" in args:
        host = args[args.index("--host") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    print(f"Starting Revenue Intelligence Inbox on http://{host}:{port}")
    uvicorn.run("app.web.app:app", host=host, port=port, reload=True)


def _print_log(log):
    print(f"  Batch: {log['batch_id']} (rev={log['batch_revision']})")
    print(f"  Inserted={log['inserted']}  Updated={log['updated']}  "
          f"Unchanged={log['unchanged']}  Skipped-older={log['skipped_older']}")
    for w in log.get("warnings", []):
        print(f"  ⚠ {w}")
