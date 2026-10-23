import pytest
from starlette.testclient import TestClient
from app.web.app import app
from app.db import get_conn

client = TestClient(app)

def test_dashboard_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Revenue Intelligence Inbox" in response.text
    assert "18" in response.text

def test_records_page():
    response = client.get("/records")
    assert response.status_code == 200
    assert "Activity Inbox" in response.text

def test_brief_page():
    response = client.get("/brief")
    assert response.status_code == 200
    assert "Manager Brief" in response.text

def test_definitions_page():
    response = client.get("/definitions")
    assert response.status_code == 200
    assert "Definitions" in response.text

def test_record_detail_page():
    with get_conn() as conn:
        row = conn.execute("SELECT source_type, source_id FROM source_record LIMIT 1").fetchone()
    if row:
        st, sid = row["source_type"], row["source_id"]
        response = client.get(f"/record/{st}/{sid}")
        assert response.status_code == 200
        assert "Metadata" in response.text
