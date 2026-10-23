"""
app/main.py — FastAPI application entrypoint.
Exposes `app` from app.web.app for standard ASGI runners (uvicorn app.main:app).
"""
import os
import uvicorn
from app.web.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
