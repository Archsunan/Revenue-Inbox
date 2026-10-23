"""
app/main.py — FastAPI application entrypoint.
Exposes `app` from app.web.app for standard ASGI runners (uvicorn app.main:app).
"""
import uvicorn
from app.web.app import app

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
