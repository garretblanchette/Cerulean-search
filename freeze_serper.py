# freeze_serper.py
# Capture top-10 Serper results per query and write to JSON.
# No LLM, no labeling. Freezes the result set so the labeler and the
# scorer both operate on the exact same URLs. Run once per benchmark
# generation; re-run only to refresh.
#
# Usage:
#   python freeze_serper.py --smoke
#   python freeze_serper.py --full
import os, json, asyncio, httpx, sys, shutil, argparse

SERPER_KEY = os.environ["SERPER_API_KEY"]
SERPER_ENDPOINT = "https://google.serper.dev/search"


async def serper_search(query, client):
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    for attempt in range(4):
        try:
            r = await client.post(SERPER_ENDPOINT, headers=headers, json={"q": query}, timeout=30.0)
            r.raise_for_status()
            data = r.json()
            results = data.get("organic", [])[:10]
            return [
                {"url": x.get("link", ""), "title": x.get("title", ""), "snippet": x.get("snippet", "")}
                for x in results
            ]
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(2 ** attempt)
    return []


async def freeze_one(query_item, http, sem):
    query = query_item["query"]
    async with sem:
        try:
            results = await serper_search(query, http)
        except Exception as e:
            return {"input": query_item, "results": [], "error": f"search failed: {str(e)[:200]}"}
    if not results:
        return {"input": query_item, "results": [], "error": "no results"}
    return {"input": query_item, "results": results}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    if args.smoke:
        in_candidates = ["benchmark/queries_smoke.json", "queries_smoke.json"]
        out_name = "frozen_serper_smoke.json"
    elif args.full:
        in_candidates = ["benchmark/queries.json", "queries.json"]
        out_name = "frozen_serper.json"
    else:
        raise SystemExit("specify --smoke or --full")

    q_path = None
    for c in in_candidates:
        if os.path.exists(c):
            q_path = c
            break
    if not q_path:
        raise SystemExit(f"queries file not found in: {in_candidates}")

    out_dir = os.path.dirname(q_path) or "."
    out_path = os.path.join(out_dir, out_name)

    if os.path.exists(out_path):
        backup = out_path.replace(".json", "_prev_backup.json")
        shutil.copy(out_path, backup)
        print(f"backed up existing {out_path} -> {backup}")

    queries = json.load(open(q_path))
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient() as http:
        tasks = [freeze_one(q, http, sem) for q in queries]
        print(f"freezing {len(tasks)} queries from {q_path}")
        frozen = []
        for i, fut in enumerate(asyncio.as_completed(tasks)):
            f = await fut
            frozen.append(f)
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(tasks)} done")

    valid = [f for f in frozen if not f.get("error")]
    errored = [f for f in frozen if f.get("error")]
    total_urls = sum(len(f.get("results", [])) for f in frozen)

    with open(out_path, "w") as f:
        json.dump(frozen, f, indent=2)

    print(f"\n=== frozen: {len(valid)} queries OK, {len(errored)} errored, {total_urls} total URLs ===")
    print(f"written: {out_path}")
    if errored:
        print("sample errors:")
        for e in errored[:3]:
            print(f"  {e['input']['query'][:50]} | {e.get('error','')[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
