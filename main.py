"""
main.py — Root FastAPI application entrypoint.
Exposes `app` from app.web.app for standard ASGI runners (uvicorn main:app, deployment platforms, etc.).
"""
import os
import uvicorn
from app.web.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=False)
