import os
import sys
from pathlib import Path

# Make the backend package importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
PUBLIC_DIR = PROJECT_ROOT / "public"

# Add backend/ to sys.path so bare imports like 'from models import ...' work
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import the FastAPI app from backend/main.py
from main import app  # noqa: E402

# Serve static files (HTML/CSS/JS) from public/
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

@app.get("/")
def serve_index():
    p = PUBLIC_DIR / "index.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html")
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/styles.css")
def styles():
    p = PUBLIC_DIR / "styles.css"
    if p.exists():
        return FileResponse(str(p), media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")

@app.get("/app.js")
def appjs():
    p = PUBLIC_DIR / "app.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/favicon.ico")
def favicon_ico():
    p = PUBLIC_DIR / "favicon.ico"
    if p.exists():
        return FileResponse(str(p))
    raise HTTPException(status_code=404)

@app.get("/favicon.png")
def favicon_png():
    p = PUBLIC_DIR / "favicon.png"
    if p.exists():
        return FileResponse(str(p), media_type="image/png")
    raise HTTPException(status_code=404)
