from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import SearchRequest, SearchResponse
from search_providers import brave_search, serper_search, ddg_search
from ranking import rerank
from summarizer import synthesize

app = FastAPI(
    title="Cerulean Search API",
    version="0.1.0",
    description="Ad-minimized, quality-weighted search API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/search", response_model=SearchResponse)
def api_search(req: SearchRequest):
    try:
        if req.provider == "brave":
            raw = brave_search(req.q, count=req.count)
        elif req.provider == "serper":
            raw = serper_search(
                req.q,
                count=req.count,
                prefer_recent_days=req.prefer_recent_days
            )
        elif req.provider == "ddg":
            raw = ddg_search(req.q, count=req.count)
        else:
            raise HTTPException(status_code=400, detail="Unsupported provider")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Search provider error: {type(e).__name__}: {e}"
        )

    ranked = rerank(req, raw)

    synthesis = []
    if req.synthesize:
        try:
            synthesis = synthesize(
                ranked,
                fetch_top_n=req.fetch_top_n,
                max_bullets=req.max_summary_bullets,
                max_chars=req.max_summary_chars
            )
        except Exception:
            synthesis = []

    return SearchResponse(
        query=req.q,
        provider=req.provider,
        results=ranked,
        synthesis=synthesis,
        meta={
            "count_requested": req.count,
            "count_returned": len(ranked),
            "no_commerce": req.no_commerce,
            "prefer_official": req.prefer_official,
            "prefer_recent_days": req.prefer_recent_days,
        },
    )
