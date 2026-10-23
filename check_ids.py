from app.db import get_conn
with get_conn() as conn:
    rows = conn.execute("SELECT record_ref, source_type, source_id FROM source_record WHERE record_ref IN ('C02', 'C04', 'M07')").fetchall()
    for r in rows:
        print(r['record_ref'], r['source_type'], r['source_id'])
