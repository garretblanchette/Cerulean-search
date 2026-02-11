import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from models import SearchRequest, SearchResponse
from search_providers import brave_search, serper_search, ddg_search
from ranking import rerank
from summarizer import synthesize

app = FastAPI(title="Cerulean Search API", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def serve_index():
    return Response(content="Cerulean Search API is running. Visit /docs for API docs.", media_type="text/plain")

@app.post("/api/search", response_model=SearchResponse)
def api_search(req: SearchRequest):
    try:
        if req.provider == "brave":
            raw = brave_search(req.q, count=req.count)
        elif req.provider == "serper":
            raw = serper_search(req.q, count=req.count, prefer_recent_days=req.prefer_recent_days)
        elif req.provider == "ddg":
            raw = ddg_search(req.q, count=req.count)
        else:
            raise HTTPException(status_code=400, detail="Unsupported provider")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider error: {type(e).__name__}: {e}")
    ranked = rerank(req, raw)
    syn = []
    if req.synthesize:
        try:
            syn = synthesize(ranked, fetch_top_n=req.fetch_top_n, max_bullets=req.max_summary_bullets, max_chars=req.max_summary_chars)
        except Exception:
            syn = []
    return SearchResponse(query=req.q, provider=req.provider, results=ranked, synthesis=syn, meta={"count_requested": req.count, "count_returned": len(ranked), "no_commerce": req.no_commerce, "prefer_official": req.prefer_official, "prefer_recent_days": req.prefer_recent_days})
