from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models import SearchRequest, SearchResponse
from backend.search_providers import brave_search, serper_search, ddg_search
from backend.ranking import rerank
from backend.summarizer import synthesize

app = FastAPI(
    title="Cerulean Search API",
    version="0.1.0",
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
    if req.provider == "brave":
        raw = brave_search(req.q, count=req.count)
    elif req.provider == "serper":
        raw = serper_search(
            req.q,
            count=req.count,
            prefer_recent_days=req.prefer_recent_days,
        )
    elif req.provider == "ddg":
        raw = ddg_search(req.q, count=req.count)
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    ranked = rerank(req, raw)

    synthesis = (
        synthesize(
            ranked,
            fetch_top_n=req.fetch_top_n,
            max_bullets=req.max_summary_bullets,
            max_chars=req.max_summary_chars,
        )
        if req.synthesize
        else []
    )

    return SearchResponse(
        query=req.q,
        provider=req.provider,
        results=ranked,
        synthesis=synthesis,
        meta={"count": len(ranked)},
    )
