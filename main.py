"""
main.py — Root FastAPI application entrypoint.
Exposes `app` from app.web.app for standard ASGI runners (uvicorn main:app, deployment platforms, etc.).
"""
import uvicorn
from app.web.app import app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
