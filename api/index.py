import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
PUBLIC_DIR = PROJECT_ROOT / "public"

for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
def root():
    return {"status": "app is running"}

@app.get("/debug")
def debug():
    info = {
        "project_root": str(PROJECT_ROOT),
        "backend_dir": str(BACKEND_DIR),
        "backend_exists": os.path.isdir(str(BACKEND_DIR)),
        "public_dir": str(PUBLIC_DIR),
        "public_exists": os.path.isdir(str(PUBLIC_DIR)),
        "sys_path": sys.path[:10],
        "files_in_root": os.listdir(str(PROJECT_ROOT)) if os.path.isdir(str(PROJECT_ROOT)) else "NOT FOUND",
    }
    try:
        info["files_in_backend"] = os.listdir(str(BACKEND_DIR))
    except Exception as e:
        info["files_in_backend"] = str(e)
    try:
        from models import SearchRequest
        info["models_import"] = "OK"
    except Exception as e:
        info["models_import"] = str(e)
    try:
        from search_providers import brave_search
        info["search_providers_import"] = "OK"
    except Exception as e:
        info["search_providers_import"] = str(e)
    return JSONResponse(info)
