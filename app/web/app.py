"""
app/web/app.py — FastAPI application factory.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from fastapi.responses import HTMLResponse
from fastapi import Request
import json as _json

from app.web.common import templates
from app.web.routes import dashboard, records, record_detail, api

from contextlib import asynccontextmanager

BASE = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-initialize database schema and seed data on startup for cloud deployment
    try:
        from app.db import ensure_db_initialized
        ensure_db_initialized()
    except Exception as e:
        print(f"Startup DB notice: {e}")
    yield


app = FastAPI(title="Revenue Intelligence Inbox", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

app.include_router(dashboard.router)
app.include_router(records.router)
app.include_router(record_detail.router)
app.include_router(api.router)


@app.get("/definitions", response_class=HTMLResponse)
async def definitions_page(request: Request):
    return templates.TemplateResponse("definitions.html", {"request": request})
