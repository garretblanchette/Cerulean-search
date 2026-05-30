# bench_v2.py - URL-level scorer for the librarian-grade Tier 1 against the v2 gold.
# Reports a CORE confidence interval (the shipping gate) with inherently contestable
# source classes (social media, personal-publishing platforms) carved into a
# separate segment that does NOT affect the core CI. Abstentions (Tier 3 territory)
# are reported, not scored, since Tier 3 is a separate stage.
import os, sys, json, argparse
sys.path.insert(0, ".")
from tier1_enhanced import tier1  # noqa: E402
sys.path.insert(0, "backend")
from source_categorizer import categorize  # noqa: E402

CONTESTED_BUCKETS = {"social", "indie"}  # scored separately, excluded from core CI

def segment(url):
    b = categorize(url)
    return b if b in CONTESTED_BUCKETS else "core"

def score(entries):
    seg = {"core": [], "social": [], "indie": []}
    abstain = {"core": 0, "social": 0, "indie": 0}
    for e in entries:
        s = segment(e["url"])
        res = tier1(e["url"])
        if res is None:
            abstain[s] += 1
            continue
        role, typ, _ = res
        seg[s].append((role == e["best_role"], typ == e["best_type"]))
    return seg, abstain

def pct(rows):
    n = len(rows)
    if not n:
        return 0, 0.0, 0.0, 0.0
    t = sum(1 for _, tk in rows if tk)
    r = sum(1 for rk, _ in rows if rk)
    b = sum(1 for rk, tk in rows if rk and tk)
    return n, t/n*100, r/n*100, b/n*100

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="benchmark/labels_smoke_gold_librarian_v2.json")
    a = ap.parse_args()
    g = json.load(open(a.gold))
    entries = g["entries"] if isinstance(g, dict) else g
    seg, abstain = score(entries)
    N = len(entries)
    n, t, r, b = pct(seg["core"])
    labeled = sum(len(v) for v in seg.values())
    print(f"gold entries: {N}   Tier1 labeled: {labeled} ({labeled/N*100:.0f}%)   "
          f"deferred to Tier3: {sum(abstain.values())}")
    print(f"\nCORE CI (shipping gate; contested carved out)")
    print(f"  scored={n}  abstain={abstain['core']}  type={t:.1f}%  role={r:.1f}%  both={b:.1f}%")
    print(f"\nCONTESTED segments (reported separately, NOT in core CI)")
    for s in ("social", "indie"):
        n, t, r, b = pct(seg[s])
        print(f"  {s:7s} scored={n:3d} abstain={abstain[s]:2d}  type={t:.1f}%  role={r:.1f}%  both={b:.1f}%")

if __name__ == "__main__":
    main()
