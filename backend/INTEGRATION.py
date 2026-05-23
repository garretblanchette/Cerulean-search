"""
INTEGRATION SKETCH - not for direct deployment.

Shows where the intent classifier, rerankers, and ambiguity detector plug
into the existing Cerulean Search pipeline at api/index.py.

Pipeline shape (existing, before this change):

    query -> sanitize -> fan-out to providers -> merge -> quality score
        -> source-type classification -> tier badge -> respond

Pipeline shape (after this change):

    query -> sanitize -> fan-out to providers -> merge -> quality score
        -> source-type classification -> classify intent -> rerank
        -> detect ambiguity -> tier badge -> respond

All new functions are pure and synchronous. No I/O, no async, no new
dependencies. Combined latency under 1ms on realistic result-set sizes.

Layers covered:
    Layer 1:   intent classifier
    Layers 2+3: list-intent reranker (entity penalty + structural detection)
    Layer 4:   editorial domain trust (folded into 2+3 feature extraction)
    Layer 5:   graded domain-match boost (NAV/ENTITY/INFO)
    Layer 6:   ambiguity detector (source-type bimodality)
"""

from typing import Any

# New imports - everything else in api/index.py stays the same.
from backend.intent_classifier import classify, IntentResult
from backend.list_intent_reranker import rerank
from backend.ambiguity_detector import detect_ambiguity, AmbiguityResult


def search_handler_sketch(
    query: str,
    raw_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Sketch of where to wire the new layers into the existing handler.

    `raw_results` is the merged, quality-scored, source-type-classified
    results from the existing pipeline. Each result must have:
        - url           str
        - title         str
        - description   str
        - quality_score float
        - source_type   str (one of the existing 10 buckets, or "Other")

    Optional but useful for the LIST reranker:
        - schema_type / type / subtype  (single-entity LocalBusiness detection)
    """

    # 1. Classify intent (~150us)
    intent: IntentResult = classify(query)

    # 2. Rerank (dispatched by intent type internally)
    #    LIST  -> entity penalty + editorial boost
    #    NAV   -> strong domain-match boost
    #    ENTITY -> moderate domain-match boost (qualifier stripped first)
    #    INFO  -> modest domain-match boost (covers lowercase brands)
    results = rerank(raw_results, intent, debug=False)

    # 3. Detect ambiguity in the source-type distribution
    #    Output drives chip emphasis in the UI; does not change ranking.
    ambiguity: AmbiguityResult = detect_ambiguity(raw_results)

    # 4. Continue with existing pipeline (tier badge).
    # The badge layer should read rerank_score with fallback to quality_score:
    #     score = r.get("rerank_score", r.get("quality_score", 0.0))

    return {
        "query": query,
        "intent": intent.to_dict(),
        "ambiguity": ambiguity.to_dict(),
        "results": results,
    }


# ----------------------------------------------------------------------
# UI integration
# ----------------------------------------------------------------------
#
# The response now carries ambiguity.is_ambiguous and ambiguity.emphasized_buckets.
# Frontend changes (app.js or whichever file owns chip rendering):
#
#   if (response.ambiguity.is_ambiguous) {
#       // Highlight matching source-type filter chips
#       for (const bucket of response.ambiguity.emphasized_buckets) {
#           const chip = document.querySelector(`[data-source-type="${bucket}"]`);
#           if (chip) chip.classList.add("chip-emphasized");
#       }
#       // Optional: explanatory line above the chip row
#       showAmbiguityHint("Multiple result types here - filter to focus.");
#   }
#
# Suggested chip-emphasized CSS:
#   .chip-emphasized {
#       border-color: var(--cerulean);
#       background: rgba(0, 123, 167, 0.08);
#   }
#
# Suppression rules:
#   - Don't emphasize if user has already selected a filter
#   - Don't re-emphasize after dismiss within the same session
#
# ----------------------------------------------------------------------
# Deployment checklist
# ----------------------------------------------------------------------
#
# 1. Copy these files to the repo's /backend directory:
#       backend/__init__.py
#       backend/intent_lexicons.py
#       backend/intent_classifier.py
#       backend/list_intent_reranker.py    (LIST + NAV + ENTITY + INFO)
#       backend/ambiguity_detector.py      (Layer 6)
#       backend/test_intent_classifier.py  (CI)
#       backend/intent_benchmark.json      (CI)
#       backend/benchmark_intent.py        (CI)
#
# 2. In api/index.py:
#       from backend.intent_classifier import classify
#       from backend.list_intent_reranker import rerank
#       from backend.ambiguity_detector import detect_ambiguity
#
#       intent = classify(query)
#       results = rerank(results, intent)
#       ambiguity = detect_ambiguity(results)
#       # ...include intent and ambiguity in JSON response
#
# 3. In the tier badge code, change score lookup:
#       score = r.get("rerank_score", r.get("quality_score", 0.0))
#
# 4. In the frontend chip-rendering code, read response.ambiguity and
#    apply chip-emphasized class when is_ambiguous is true.
#
# 5. No new Python dependencies. Pure stdlib. Vercel config unchanged.
#
# 6. Rollback: revert api/index.py and frontend chip logic. The backend
#    files are inert without wiring.
#
# ----------------------------------------------------------------------
# What changes by intent type
# ----------------------------------------------------------------------
#
# LIST   - "[category] in [location]" -> entity penalty + editorial boost
#          Eater LA goes from #8 to #3 for "palm springs restaurants"
# NAV    - capitalized brand -> strong canonical-SLD boost
#          ebay.com goes from #10 to #1 for "Ebay"
# ENTITY - "[brand] [qualifier]" -> moderate SLD boost (qualifier stripped)
#          starbucks.com surfaces for "Starbucks hours"
# INFO   - bare query or lowercase brand -> modest SLD boost
#          ebay.com surfaces for lowercase "ebay" (was buried)
#          apple.com surfaces for lowercase "apple", with chips emphasized
#
# ----------------------------------------------------------------------
# Tuning knobs
# ----------------------------------------------------------------------
#
# list_intent_reranker.py:
#   _ENTITY_PENALTY_STRENGTH    = 0.55   # LIST: multiplicative downweight
#   _EDITORIAL_BOOST_STRENGTH   = 0.45   # LIST: additive boost
#   _NAV_BOOST_STRENGTH         = 2.5    # peak domain-match boost
#   _INTENT_BOOST_FACTORS       = {NAV: 1.0, ENTITY: 0.4, INFO: 0.3, LIST: 0.0}
#
# ambiguity_detector.py:
#   _MIN_BUCKET_SHARE           = 0.20   # bucket significance threshold
#   _MAX_RATIO_TO_LARGEST       = 3.0    # bucket comparability threshold
#   _MIN_TOTAL_RESULTS          = 5      # below this, don't trigger
#
# All tunable; A/B once click data is available.

