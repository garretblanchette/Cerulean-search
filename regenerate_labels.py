# regenerate_labels.py - generate benchmark labels from actual Serper results
# Labeler is Gemini Flash (heavier than the Flash-Lite classifier).
# Bounds are set as labeler's actual classification distribution +/- TOLERANCE_PCT.
import os, json, asyncio, httpx, sys, shutil
 
GEMINI_KEY = os.environ["BENCHMARK_LABELER_API_KEY"]
SERPER_KEY = os.environ["SERPER_API_KEY"]
LABELER_MODEL = "gemini-2.5-flash-lite"
SERPER_ENDPOINT = "https://google.serper.dev/search"
TOLERANCE_PCT = 15
 
LABELER_PROMPT = """You are the careful, deliberate labeler for a search-result classification benchmark. Take more reasoning time than a fast runtime classifier would.
 
ROLE (how close to original evidence):
- PRIMARY: original materials. Court filings, datasets, raw reports, original interviews, original research articles in scientific journals, statutes, original creative works, official communications from the entity itself.
- SECONDARY: analysis or interpretation of primary sources. Editorial journalism, academic books and review articles, expert commentary, analytical pieces.
- TERTIARY: summaries or syntheses of secondary sources. Encyclopedias, Wikipedia, dictionary entries, listicles, "what is X" guides, AI summaries.
- UNCLASSIFIED: confidence too low.
 
TYPE (what kind of entity):
- PRIMARY_SOURCE_PUBLISHER: government data portals, court databases, journal publishers, statute repositories, raw dataset hosts.
- JOURNALISM: editorial process, byline, original reporting.
- ACADEMIC: research institutions, academic publishers, peer-reviewed venues.
- REFERENCE: Wikipedia, MDN, SEP, encyclopedic works.
- INDIE: personal blogs, neocities, github.io, IndieWeb participants.
- COMMUNITY: Reddit, Hacker News, Stack Overflow, forums.
- COMMERCIAL: corporate sites, product pages, marketing.
- AGGREGATOR: lyric sites, recipe aggregators, content repackagers.
- SEO_FARM: AI-generated content farms, listicle factories, thin affiliates.
- UNCLASSIFIED: confidence too low.
 
Consider URL structure, domain reputation, title/snippet content. Two or more signals must point the same way for a confident label. When uncertain, prefer UNCLASSIFIED over guessing."""
 
ROLES = ["PRIMARY", "SECONDARY", "TERTIARY", "UNCLASSIFIED"]
TYPES = ["PRIMARY_SOURCE_PUBLISHER", "JOURNALISM", "ACADEMIC", "REFERENCE", "INDIE", "COMMUNITY", "COMMERCIAL", "AGGREGATOR", "SEO_FARM", "UNCLASSIFIED"]
ROLE_KEYS = ["primary", "secondary", "tertiary", "unclassified"]
TYPE_KEYS = ["primary_source_publisher", "journalism", "academic", "reference", "indie", "community", "commercial", "aggregator", "seo_farm", "unclassified"]
 
 
async def serper_search(query, client):
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    for attempt in range(4):
        try:
            r = await client.post(SERPER_ENDPOINT, headers=headers, json={"q": query}, timeout=30.0)
            r.raise_for_status()
            data = r.json()
            results = data.get("organic", [])[:10]
            return [{"url": x.get("link",""), "title": x.get("title",""), "snippet": x.get("snippet","")} for x in results]
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(2 ** attempt)
    return []
 
 
async def label_one(result, sem, client):
    user_msg = f"URL: {result['url']}\nTITLE: {result['title']}\nSNIPPET: {result['snippet']}\n\nReturn JSON: {{\"role\": \"...\", \"type\": \"...\"}}"
    body = {
        "system_instruction": {"parts": [{"text": LABELER_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 200, "responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}}
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{LABELER_MODEL}:generateContent?key={GEMINI_KEY}"
    async with sem:
        for attempt in range(4):
            try:
                r = await client.post(url, json=body, timeout=60.0)
                if r.status_code == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = r.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                p = json.loads(text)
                return {
                    "role": str(p.get("role","UNCLASSIFIED")).upper().replace(" ","_"),
                    "type": str(p.get("type","UNCLASSIFIED")).upper().replace(" ","_"),
                }
            except Exception as e:
                if attempt == 3:
                    return {"role": "UNCLASSIFIED", "type": "UNCLASSIFIED", "error": str(e)[:200]}
                await asyncio.sleep(2 ** attempt)
        return {"role": "UNCLASSIFIED", "type": "UNCLASSIFIED", "error": "exhausted"}
 
 
def distribution(classifications, key):
    n = len(classifications) or 1
    counts = {}
    for c in classifications:
        v = c.get(key, "UNCLASSIFIED")
        counts[v] = counts.get(v, 0) + 1
    keys = ROLES if key == "role" else TYPES
    return {k: (counts.get(k, 0) / n) * 100 for k in keys}
 
 
def to_bounds(dist, keys, tolerance):
    bounds = {}
    for k in keys:
        actual = dist.get(k.upper(), 0)
        bounds[f"{k}_min"] = int(max(0, actual - tolerance))
        bounds[f"{k}_max"] = int(min(100, actual + tolerance))
    return bounds
 
 
async def generate_label(query_item, http, sem):
    query = query_item["query"]
    try:
        results = await serper_search(query, http)
    except Exception as e:
        return {"input": query_item, "label": None, "error": f"search failed: {str(e)[:200]}"}
    if not results:
        return {"input": query_item, "label": None, "error": "no results"}
 
    classifications = await asyncio.gather(*[label_one(r, sem, http) for r in results])
    role_dist = distribution(classifications, "role")
    type_dist = distribution(classifications, "type")
    role_pct = to_bounds(role_dist, ROLE_KEYS, TOLERANCE_PCT)
    type_pct = to_bounds(type_dist, TYPE_KEYS, TOLERANCE_PCT)
 
    return {
        "input": query_item,
        "label": {
            "query": query,
            "category": query_item.get("category"),
            "reasoning": {
                "method": "labeler_classified_actual_serper_results",
                "tolerance_pct": TOLERANCE_PCT,
                "labeler_model": LABELER_MODEL,
                "actual_role_dist": role_dist,
                "actual_type_dist": type_dist,
            },
            "expected_top_10": {"role_pct": role_pct, "type_pct": type_pct}
        }
    }
 
 
async def main():
    smoke = "--smoke" in sys.argv
    full = "--full" in sys.argv
 
    if smoke:
        in_candidates = ["benchmark/queries_smoke.json", "queries_smoke.json"]
        out_path = None
    elif full:
        in_candidates = ["benchmark/queries.json", "queries.json"]
        out_path = None
    else:
        raise SystemExit("specify --smoke or --full")
 
    q_path = None
    for c in in_candidates:
        if os.path.exists(c):
            q_path = c
            break
    if not q_path:
        raise SystemExit(f"queries file not found in: {in_candidates}")
 
    # output file path mirrors input
    if smoke:
        out_path = q_path.replace("queries_smoke", "labels_smoke")
    else:
        out_path = q_path.replace("queries.json", "labels.json")
 
    # back up existing labels file if present
    if os.path.exists(out_path):
        backup = out_path.replace(".json", "_v1_backup.json")
        if not os.path.exists(backup):
            shutil.copy(out_path, backup)
            print(f"backed up existing {out_path} -> {backup}")
 
    queries = json.load(open(q_path))
    sem = asyncio.Semaphore(8)
 
    async with httpx.AsyncClient() as http:
        tasks = [generate_label(q, http, sem) for q in queries]
        print(f"labeling {len(tasks)} queries with model={LABELER_MODEL}, tolerance=+/-{TOLERANCE_PCT}%")
        labels = []
        for i, fut in enumerate(asyncio.as_completed(tasks)):
            l = await fut
            labels.append(l)
            if (i + 1) % 5 == 0:
                print(f"  {i+1}/{len(tasks)} done")
 
    valid = [l for l in labels if l.get("label")]
    errored = [l for l in labels if not l.get("label")]
 
    with open(out_path, "w") as f:
        json.dump(valid, f, indent=2)
 
    print(f"\n=== {len(valid)} labels written, {len(errored)} errored ===")
    print(f"written: {out_path}")
    if errored:
        print("sample errors:")
        for e in errored[:3]:
            print(f"  {e['input']['query'][:50]} | {e.get('error','')[:80]}")
 
 
if __name__ == "__main__":
    asyncio.run(main())
 