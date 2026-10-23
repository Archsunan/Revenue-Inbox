"""
app/web/common.py — Shared Jinja2 template environment and filters.
"""
import json
from pathlib import Path
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Custom Jinja filter for parsing JSON strings in templates
def from_json(val):
    if not val:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return []

templates.env.filters["from_json"] = from_json
