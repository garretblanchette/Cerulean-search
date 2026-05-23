import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from models import SearchRequest, SearchResponse
from search_providers import brave_search, serper_search, ddg_search
from ai_detector import score_results
from ranking import rerank
from summarizer import synthesize
from topic_extractor import extract_topic
from intent_classifier import classify, Intent
from list_intent_reranker import rerank as intent_rerank
from ambiguity_detector import detect_ambiguity

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

    # Layers 1-6: intent-based reranking.
    # LIST queries: demote single-entity homepages, boost editorial guides.
    # NAVIGATIONAL queries: lift canonical destination (ebay.com for "ebay").
    # ENTITY/INFORMATIONAL: pass through unchanged.
    intent = classify(req.q)
    if intent.intent in (Intent.LIST, Intent.NAVIGATIONAL):
        result_dicts = [{
            "url": str(r.url),
            "title": r.title,
            "snippet": r.snippet,
            "description": r.snippet,
            "quality_score": r.score,
            "source_type": r.source_type,
        } for r in ranked]
        reranked = intent_rerank(result_dicts, intent)
        score_by_url = {d["url"]: d.get("rerank_score") for d in reranked}
        for r in ranked:
            new_score = score_by_url.get(str(r.url))
            if new_score is not None:
                r.score = float(new_score)
                r.reasons = r.reasons + [f"intent:{intent.intent.value}"]
        ranked.sort(key=lambda r: r.score, reverse=True)

    # Layer 6: ambiguity detection on the source-type distribution.
    # Hint for the UI to emphasize filter chips on ambiguous queries.
    ambiguity = detect_ambiguity(
        [{"source_type": r.source_type} for r in ranked]
    )

    # Source-type filter (applied after ranking, before summarization).
    # Empty list = no filter. Set membership lets the UI multi-select.
    if req.source_types:
        allowed = set(req.source_types)
        ranked = [r for r in ranked if r.source_type in allowed]

    # Topic descriptors: cheap, no body fetch. Populated only when summarize=on.
    # Frontend renders Topic callout only when topic is non-null.
    if req.synthesize:
        for r in ranked:
            try:
                r.topic = extract_topic(r.title, r.snippet)
            except Exception:
                r.topic = None

    syn = []
    if req.synthesize:
        try:
            syn = synthesize(ranked, fetch_top_n=req.fetch_top_n, max_bullets=req.max_summary_bullets, max_chars=req.max_summary_chars)
        except Exception:
            syn = []
    score_results(ranked)
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
            "quality_boost": req.quality_boost,
            "source_types": req.source_types,
            "prefer_recent_days": req.prefer_recent_days,
            "intent": intent.to_dict(),
            "ambiguity": ambiguity.to_dict(),
        },
    )
