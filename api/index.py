import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
PUBLIC_DIR = PROJECT_ROOT / "public"

for p in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

try:
    from backend.models import SearchRequest, SearchResponse
    from backend.search_providers import brave_search, serper_search, ddg_search
    from backend.ranking import rerank
    from backend.summarizer import synthesize
except Exception:
    from models import SearchRequest,
