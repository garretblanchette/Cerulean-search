# bench.py - Serper search + Gemini Flash classifier
import os, json, asyncio, argparse, httpx

GEMINI_KEY = os.environ["BENCHMARK_LABELER_API_KEY"]
SERPER_KEY = os.environ["SERPER_API_KEY"]
MODEL = "gemini-2.5-flash"
SERPER_ENDPOINT = "https://google.serper.dev/search"

CLASSIFIER_PROMPT = """You classify a single search result by source role and source type.

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

Two or more signals must point the same way for a confident label."""

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


async def classify(result, sem, client):
    user_msg = f"URL: {result['url']}\nTITLE: {result['title']}\nSNIPPET: {result['snippet']}\n\nReturn JSON: {{\"role\": \"...\", \"type\": \"...\"}}"
    body = {
        "system_instruction": {"parts": [{"text": CLASSIFIER_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 200, "responseMimeType": "application/json"}
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}"
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


def check_bounds(dist, bounds, label_keys):
    failures = []
    for lk in label_keys:
        mn = bounds.get(f"{lk}_min")
        mx = bounds.get(f"{lk}_max")
        actual = dist.get(lk.upper(), 0)
        if mn is not None and actual < mn:
            failures.append(f"{lk}: {actual:.0f}% < min {mn}%")
        if mx is not None and actual > mx:
            failures.append(f"{lk}: {actual:.0f}% > max {mx}%")
    return (len(failures) == 0, failures)


async def score_query(item, label, http, classify_sem, search_sem):
    query = item["query"]
    try:
        async with search_sem:
            results = await serper_search(query, http)
    except Exception as e:
        return {"query": query, "error": f"search failed: {str(e)[:200]}", "role_pass": False, "type_pass": False}
    if not results:
        return {"query": query, "error": "no results", "role_pass": False, "type_pass": False}

    classifications = await asyncio.gather(*[classify(r, classify_sem, http) for r in results])
    role_dist = distribution(classifications, "role")
    type_dist = distribution(classifications, "type")
    role_bounds = label["label"]["expected_top_10"]["role_pct"]
    type_bounds = label["label"]["expected_top_10"]["type_pct"]
    role_pass, role_fail = check_bounds(role_dist, role_bounds, ROLE_KEYS)
    type_pass, type_fail = check_bounds(type_dist, type_bounds, TYPE_KEYS)

    return {
        "query": query, "category": item.get("category"), "difficulty": item.get("difficulty"),
        "role_dist": role_dist, "type_dist": type_dist,
        "role_pass": role_pass, "type_pass": type_pass,
        "role_failures": role_fail, "type_failures": type_fail,
        "n_results": len(results),
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--classify-concurrency", type=int, default=8)
    ap.add_argument("--search-concurrency", type=int, default=8)
    args = ap.parse_args()

    if args.smoke:
        candidates = [("benchmark/queries_smoke.json", "benchmark/labels_smoke.json"),
                      ("queries_smoke.json", "labels_smoke.json")]
    elif args.full:
        candidates = [("benchmark/queries.json", "benchmark/labels.json"),
                      ("queries.json", "labels.json")]
    else:
        raise SystemExit("specify --smoke or --full")

    q_path = l_path = None
    for q, l in candidates:
        if os.path.exists(q) and os.path.exists(l):
            q_path, l_path = q, l
            break
    if not q_path:
        raise SystemExit(f"files not found in any of: {candidates}")

    out = "bench_results_smoke.json" if args.smoke else "bench_results_full.json"

    queries = json.load(open(q_path))
    labels = json.load(open(l_path))
    label_by_q = {l["input"]["query"]: l for l in labels}

    classify_sem = asyncio.Semaphore(args.classify_concurrency)
    search_sem = asyncio.Semaphore(args.search_concurrency)

    async with httpx.AsyncClient() as http:
        tasks = []
        for q in queries:
            lab = label_by_q.get(q["query"])
            if not lab:
                continue
            tasks.append(score_query(q, lab, http, classify_sem, search_sem))

        print(f"running {len(tasks)} queries, model={MODEL}, search=serper")
        results = []
        for i, fut in enumerate(asyncio.as_completed(tasks)):
            r = await fut
            results.append(r)
            if (i + 1) % 5 == 0:
                print(f"  {i+1}/{len(tasks)} done")

    role_pass = sum(1 for r in results if r.get("role_pass"))
    type_pass = sum(1 for r in results if r.get("type_pass"))
    errors = sum(1 for r in results if r.get("error"))
    n = len(results)
    summary = {
        "n": n, "model": MODEL, "errors": errors,
        "role_accuracy": role_pass / n if n else 0,
        "type_accuracy": type_pass / n if n else 0,
        "role_gate_hit": (role_pass / n if n else 0) >= 0.85,
        "type_gate_hit": (type_pass / n if n else 0) >= 0.90,
    }

    with open(out, "w") as f:
        json.dump({"summary": summary, "per_query": results}, f, indent=2)

    print(f"\n=== {n} queries, model={MODEL} ===")
    print(f"errors: {errors}")
    print(f"role: {role_pass}/{n} = {summary['role_accuracy']*100:.1f}%  gate 85%  {'HIT' if summary['role_gate_hit'] else 'MISS'}")
    print(f"type: {type_pass}/{n} = {summary['type_accuracy']*100:.1f}%  gate 90%  {'HIT' if summary['type_gate_hit'] else 'MISS'}")
    print(f"written: {out}")


if __name__ == "__main__":
    asyncio.run(main())
