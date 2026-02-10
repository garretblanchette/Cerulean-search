import os
import sys

# Vercel serverless entrypoint.
# Make imports robust regardless of working directory and whether /backend is a package.
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

for p in (PROJECT_ROOT, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

# Import backend modules with a two-path fallback:
try:
    from backend.models import SearchRequest, SearchResponse  # type: ignore
    from backend.search_providers import brave_search, serper_search, ddg_search  # type: ignore
    from backend.ranking import rerank  # type: ignore
    from backend.summarizer import synthesize  # type: ignore
except Exception:
    # If backend isn't a package (no __init__.py), import from BACKEND_DIR directly
    from models import SearchRequest, SearchResponse  # type: ignore
    from search_providers import brave_search, serper_search, ddg_search  # type: ignore
    from ranking import rerank  # type: ignore
    from summarizer import synthesize  # type: ignore

app = FastAPI(
    title="Cerulean Search API",
    version="0.1.0",
    description="Ad-minimized, quality-weighted search API (Vercel serverless entrypoint).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

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
            syn = synthesize(
                ranked,
                fetch_top_n=req.fetch_top_n,
                max_bullets=req.max_summary_bullets,
                max_chars=req.max_summary_chars,
            )
        except Exception:
            syn = []

    return SearchResponse(
        query=req.q,
        provider=req.provider,
        results=ranked,
        synthesis=syn,
        meta={
            "count_requested": req.count,
            "count_returned": len(ranked),
            "no_commerce": req.no_commerce,
            "prefer_official": req.prefer_official,
            "prefer_recent_days": req.prefer_recent_days,
        },
    )
