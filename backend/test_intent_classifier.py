"""
Tests for the Cerulean Search intent classifier and list-intent reranker.

Run with: pytest backend/test_intent_classifier.py -v
"""

from __future__ import annotations

import pytest

from backend.intent_classifier import Intent, classify
from backend.list_intent_reranker import (
    apply_graded_domain_boost,
    extract_features,
    rerank,
    rerank_for_list_intent,
    rerank_for_navigational_intent,
)
from backend.ambiguity_detector import detect_ambiguity


# ----------------------------------------------------------------------
# Classifier: list intent
# ----------------------------------------------------------------------

class TestListIntent:
    def test_canonical_pattern_palm_springs(self):
        r = classify("palm springs restaurants")
        assert r.intent is Intent.LIST
        assert r.confidence >= 0.85
        assert r.category == "restaurants"
        assert r.location is not None

    def test_in_location_pattern(self):
        r = classify("restaurants in Palm Springs")
        assert r.intent is Intent.LIST
        assert r.confidence >= 0.85
        assert r.category == "restaurants"
        assert r.location == "Palm Springs"

    def test_near_me(self):
        r = classify("coffee shops near me")
        assert r.intent is Intent.LIST
        assert r.location == "__GEOLOCATION__"
        assert r.signals.has_near_me

    def test_best_modifier_singular(self):
        r = classify("best restaurant in Austin")
        assert r.intent is Intent.LIST
        assert "best" in r.modifiers
        assert r.category == "restaurants"  # singular -> plural canonical

    def test_top_n_pattern(self):
        r = classify("top 10 ramen NYC")
        assert r.intent is Intent.LIST
        assert r.signals.has_count_pattern
        assert r.confidence >= 0.9

    def test_things_to_do(self):
        r = classify("things to do in Tokyo")
        assert r.intent is Intent.LIST
        assert r.category == "things to do"
        assert r.location == "Tokyo"

    def test_bare_category(self):
        # "restaurants" alone - weak list intent, still list
        r = classify("restaurants")
        assert r.intent is Intent.LIST

    def test_where_to_eat(self):
        # Could be a multi-word modifier in future; baseline behavior:
        # currently question word at start makes this INFORMATIONAL.
        # Test exists to document current behavior, not lock it in.
        r = classify("where to eat in Brooklyn")
        # Either INFORMATIONAL or LIST is defensible; assert it's not ENTITY
        assert r.intent is not Intent.ENTITY


# ----------------------------------------------------------------------
# Classifier: entity intent
# ----------------------------------------------------------------------

class TestEntityIntent:
    def test_brand_hours(self):
        r = classify("starbucks hours")
        assert r.intent is Intent.ENTITY
        assert r.confidence >= 0.85

    def test_brand_menu(self):
        r = classify("Farm Palm Springs menu")
        assert r.intent is Intent.ENTITY

    def test_brand_reservations(self):
        r = classify("spencer's reservations")
        assert r.intent is Intent.ENTITY

    def test_branded_navigational(self):
        r = classify("OpenTable")
        # Single capitalized token, no category, no qualifier
        assert r.intent in (Intent.NAVIGATIONAL, Intent.ENTITY)


# ----------------------------------------------------------------------
# Classifier: informational and navigational
# ----------------------------------------------------------------------

class TestOtherIntents:
    def test_how_question(self):
        r = classify("how does photosynthesis work")
        assert r.intent is Intent.INFORMATIONAL

    def test_what_question(self):
        r = classify("what is the capital of France")
        assert r.intent is Intent.INFORMATIONAL

    def test_empty_query(self):
        r = classify("")
        assert r.intent is Intent.INFORMATIONAL
        assert r.confidence == 0.0


# ----------------------------------------------------------------------
# Classifier: edge cases
# ----------------------------------------------------------------------

class TestClassifierEdgeCases:
    def test_only_whitespace(self):
        r = classify("   ")
        assert r.intent is Intent.INFORMATIONAL

    def test_very_long_query(self):
        q = "best italian restaurants for date night with outdoor seating in palm springs california"
        r = classify(q)
        assert r.intent is Intent.LIST
        assert r.category in {"restaurants"}

    def test_location_with_state_code(self):
        r = classify("restaurants Palm Springs CA")
        assert r.intent is Intent.LIST
        assert r.location is not None
        assert "Palm Springs" in r.location

    def test_capitalization_insensitive(self):
        r = classify("BEST PIZZA IN BROOKLYN")
        # Location detection here depends on caps; this test documents that
        # uppercase-only queries lose location info but still classify LIST
        assert r.intent is Intent.LIST


# ----------------------------------------------------------------------
# Reranker: feature extraction
# ----------------------------------------------------------------------

class TestFeatureExtraction:
    def test_farmpalmsprings_signals(self):
        """Canonical bad result from the screenshot."""
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://farmpalmsprings.com/",
            "title": "Farm - Palm Springs, CA",
            "description": (
                "Due to the size of our restaurant all catering inquires will be "
                "ran through our sister restaurant Clandestino."
            ),
        }
        f = extract_features(result, intent)
        assert f.title_matches_entity_pattern
        assert f.snippet_entity_signals >= 1  # "our restaurant"
        assert f.domain_contains_location  # palmsprings in domain
        assert f.url_at_root
        assert f.entity_homepage_score >= 0.6

    def test_spencers_signals(self):
        """Even stronger entity signals - phone, address, copyright in snippet."""
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://www.spencersrestaurant.com/",
            "title": "Spencer's Restaurant",
            "description": (
                "Spencer's Restaurant 701 West Baristo Road, Palm Springs CA 92262 "
                "(760) 327-3446 phone | © Copyright 2007 - 2026 All Rights Reserved."
            ),
        }
        f = extract_features(result, intent)
        assert f.snippet_entity_signals >= 3  # phone, address, copyright, city+state+zip
        assert f.domain_contains_category  # "restaurant" in domain
        assert f.entity_homepage_score >= 0.7

    def test_clandestino_signals(self):
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://clandestinopalmsprings.com/",
            "title": "Clandestino - Palm Springs, CA",
            "description": (
                "We love people and their stories. Our first restaurant adventure "
                "was FARM, also located in downtown Palm Springs."
            ),
        }
        f = extract_features(result, intent)
        assert f.title_matches_entity_pattern
        assert f.domain_contains_location
        assert f.entity_homepage_score >= 0.55

    def test_michelin_signals(self):
        """Editorial result should score editorial, not entity."""
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://guide.michelin.com/us/en/california/palm-springs/restaurants",
            "title": "Palm Springs MICHELIN Restaurants - The MICHELIN Guide USA",
            "description": (
                "Starred restaurants, Bib Gourmand and all the MICHELIN restaurants "
                "in Palm Springs on the MICHELIN Guide's official website."
            ),
        }
        f = extract_features(result, intent)
        assert f.domain_is_known_editorial
        assert f.editorial_score >= 0.6
        assert f.entity_homepage_score == 0.0  # allow-listed

    def test_eater_signals(self):
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://la.eater.com/maps/best-restaurants-palm-springs-coachella-valley",
            "title": "The Best Restaurants in Palm Springs, According to Eater Editors | Eater LA",
            "description": (
                "At the family-owned restaurant, find pastas, a New York strip steak, "
                "steamed mussels, salads."
            ),
        }
        f = extract_features(result, intent)
        assert f.domain_is_known_editorial
        assert f.title_matches_editorial_pattern
        assert f.editorial_score >= 0.7

    def test_visitpalmsprings_signals(self):
        """Official tourism domain pattern."""
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://www.visitpalmsprings.com/dining/",
            "title": "Dining In Palm Springs - Visit Palm Springs",
            "description": "Palm Springs dining blends local flavor, midcentury charm.",
        }
        f = extract_features(result, intent)
        assert f.domain_is_official_tourism
        assert f.editorial_score >= 0.3

    def test_personal_blog_editorial_title(self):
        """Editorial title pattern without known domain."""
        intent = classify("palm springs restaurants")
        result = {
            "url": "https://oliviamichelleh.com/foodies-guide-palm-springs/",
            "title": "A Foodie's Guide to Palm Springs - Olivia Michelle",
            "description": "Lulu's California Bistro - has an extensive menu.",
        }
        f = extract_features(result, intent)
        assert f.title_matches_editorial_pattern
        assert f.editorial_score >= 0.25


# ----------------------------------------------------------------------
# Reranker: end-to-end on the screenshot SERP
# ----------------------------------------------------------------------

# This is the actual result set from the Palm Springs screenshot,
# in the order they appeared on the page.
SCREENSHOT_SERP = [
    {
        "url": "https://www.visitpalmsprings.com/dining/",
        "title": "Dining In Palm Springs - Visit Palm Springs",
        "description": "Palm Springs dining blends local flavor, midcentury charm, and a welcoming spirit, all set within the ancestral lands of the Agua Caliente Band of Cahuilla Indians.",
        "quality_score": 0.95,
    },
    {
        "url": "https://guide.michelin.com/us/en/california/palm-springs/restaurants",
        "title": "Palm Springs MICHELIN Restaurants - The MICHELIN Guide USA",
        "description": "Starred restaurants, Bib Gourmand and all the MICHELIN restaurants in Palm Springs on the MICHELIN Guide's official website.",
        "quality_score": 0.92,
    },
    {
        "url": "https://oliviamichelleh.com/foodies-guide-palm-springs/",
        "title": "A Foodie's Guide to Palm Springs - Olivia Michelle",
        "description": "Lulu's California Bistro 200 S Palm Canyon Drive, Palm Springs CA 92262 Lulu's has an extensive menu and offers breakfast, brunch, lunch and dinner.",
        "quality_score": 0.78,
    },
    {
        "url": "https://farmpalmsprings.com/",
        "title": "Farm - Palm Springs, CA",
        "description": "Due to the size of our restaurant all catering inquires will be ran through our sister restaurant Clandestino. This is a must go in Palm Springs.",
        "quality_score": 0.55,
    },
    {
        "url": "https://clandestinopalmsprings.com/",
        "title": "Clandestino - Palm Springs, CA",
        "description": "We love people and their stories. Our first restaurant venture was FARM, also located in downtown Palm Springs.",
        "quality_score": 0.55,
    },
    {
        "url": "https://www.spencersrestaurant.com/",
        "title": "Spencer's Restaurant",
        "description": "Spencer's Restaurant 701 West Baristo Road, Palm Springs CA 92262 (760) 327-3446 phone | © Copyright 2007 - 2026 All Rights Reserved.",
        "quality_score": 0.55,
    },
    {
        "url": "https://www.eight4nine.com/",
        "title": "Eight4Nine Restaurant & Lounge",
        "description": "Located in the fashionable Uptown Design District of Palm Springs, Eight4Nine Restaurant & Lounge has proudly earned a 5-star rating.",
        "quality_score": 0.55,
    },
    {
        "url": "https://la.eater.com/maps/best-restaurants-palm-springs-coachella-valley",
        "title": "The Best Restaurants in Palm Springs, According to Eater Editors | Eater LA",
        "description": "At the family-owned restaurant, find pastas, a New York strip steak, steamed mussels, salads.",
        "quality_score": 0.70,
    },
]


class TestEndToEndRerank:
    def test_eater_promoted(self):
        """Eater list should be ranked above the entity homepages."""
        intent = classify("palm springs restaurants")
        ranked = rerank_for_list_intent(SCREENSHOT_SERP, intent, debug=True)

        # Find positions
        urls = [r["url"] for r in ranked]
        eater_pos = next(i for i, u in enumerate(urls) if "eater.com" in u)
        farm_pos = next(i for i, u in enumerate(urls) if "farmpalmsprings" in u)
        clandestino_pos = next(i for i, u in enumerate(urls) if "clandestino" in u)
        spencer_pos = next(i for i, u in enumerate(urls) if "spencersrestaurant" in u)
        eight4nine_pos = next(i for i, u in enumerate(urls) if "eight4nine" in u)

        # All four entity homepages must rank below the Eater editorial
        assert eater_pos < farm_pos
        assert eater_pos < clandestino_pos
        assert eater_pos < spencer_pos
        assert eater_pos < eight4nine_pos

    def test_editorial_results_top_three(self):
        intent = classify("palm springs restaurants")
        ranked = rerank_for_list_intent(SCREENSHOT_SERP, intent)
        top_three_urls = [r["url"] for r in ranked[:3]]
        # Top three should be editorial-leaning
        assert any("visitpalmsprings.com" in u for u in top_three_urls)
        assert any("michelin.com" in u for u in top_three_urls)
        assert any("eater.com" in u for u in top_three_urls)

    def test_entity_homepages_in_bottom_half(self):
        intent = classify("palm springs restaurants")
        ranked = rerank_for_list_intent(SCREENSHOT_SERP, intent)
        n = len(ranked)
        urls = [r["url"] for r in ranked]
        bad_domains = ["farmpalmsprings", "clandestino", "spencersrestaurant", "eight4nine"]
        for bad in bad_domains:
            pos = next(i for i, u in enumerate(urls) if bad in u)
            assert pos >= n // 2, f"{bad} ranked at {pos}, expected bottom half"

    def test_non_list_intent_passes_through(self):
        intent = classify("starbucks hours")
        assert intent.intent is Intent.ENTITY
        # Reranker should no-op for non-list intent
        ranked = rerank_for_list_intent(SCREENSHOT_SERP, intent)
        assert [r["url"] for r in ranked] == [r["url"] for r in SCREENSHOT_SERP]

    def test_debug_features_attached(self):
        intent = classify("palm springs restaurants")
        ranked = rerank_for_list_intent(SCREENSHOT_SERP, intent, debug=True)
        for r in ranked:
            assert "rerank_score" in r
            assert "rerank_features" in r

    def test_does_not_mutate_input(self):
        intent = classify("palm springs restaurants")
        before = [dict(r) for r in SCREENSHOT_SERP]
        _ = rerank_for_list_intent(SCREENSHOT_SERP, intent)
        # Inputs unchanged
        for orig, after in zip(before, SCREENSHOT_SERP):
            assert orig == after


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ----------------------------------------------------------------------
# Navigational reranker tests
# ----------------------------------------------------------------------

# Actual SERP from the "Ebay" query screenshot, in original order.
# Quality scores estimated from the displayed badges (Fair ~ 0.55,
# unbadged-Commercial ~ 0.30).
EBAY_SERP = [
    {
        "url": "https://www.instagram.com/ebay/",
        "title": "eBay (@ebay) - Instagram photos and videos",
        "description": "1M Followers, 95 Following, 4,238 Posts - eBay (@ebay) on Instagram",
        "quality_score": 0.55,
    },
    {
        "url": "https://en.wikipedia.org/wiki/EBay",
        "title": "eBay - Wikipedia",
        "description": "eBay Inc. is an American multinational e-commerce company based in San Jose, California, that allows users to buy or view items via retail sales through online marketplaces and websites in 190 markets worldwide.",
        "quality_score": 0.55,
    },
    {
        "url": "https://www.ebayinc.com/",
        "title": "About eBay: Company Info, News, Careers, Investor Relations",
        "description": "Information and news about eBay Inc. (Nasdaq: EBAY), a global commerce leader.",
        "quality_score": 0.55,
    },
    {
        "url": "https://finance.yahoo.com/quote/EBAY",
        "title": "eBay Inc. (EBAY) Stock Price, News, Quote & History - Yahoo Finance",
        "description": "The company's platforms enable users to list, sell, buy, and pay various products.",
        "quality_score": 0.55,
    },
    {
        "url": "https://www.facebook.com/ebay/",
        "title": "eBay | Facebook",
        "description": "eBay. 10,776,626 likes - 13,563 talking about this.",
        "quality_score": 0.55,
    },
    {
        "url": "https://play.google.com/store/apps/details?id=com.ebay.mobile",
        "title": "eBay online shopping & selling - Apps on Google Play",
        "description": "Life's easier in the eBay app, buy and sell millions of items on the go!",
        "quality_score": 0.55,
    },
    {
        "url": "https://www.nytimes.com/2024/05/15/business/ebay-collectibles.html",
        "title": "EBay, the Old-School E-Commerce Site, Finds Its Place in Modern Retail",
        "description": "The online marketplace has remade itself by focusing on collectibles and other high-end goods.",
        "quality_score": 0.55,
    },
    {
        "url": "https://www.prnewswire.com/news-releases/ebay-rejects-proposal",
        "title": "eBay Rejects Unsolicited Proposal from GameStop",
        "description": "About eBay eBay Inc. (Nasdaq: EBAY) is a global commerce leader.",
        "quality_score": 0.55,
    },
    {
        "url": "https://apps.apple.com/us/app/ebay-online-shopping/id282614216",
        "title": "eBay online shopping & selling App - App Store",
        "description": "Life's easier in the eBay app, buy and sell millions of items on the go.",
        "quality_score": 0.30,
    },
    {
        "url": "https://www.ebay.com/",
        "title": "Electronics, Cars, Fashion, Collectibles & More | eBay",
        "description": "Buy & sell electronics, cars, clothes, collectibles & more on eBay, the world's online marketplace.",
        "quality_score": 0.30,
    },
]


class TestNavigationalIntent:
    """Brand-name navigational queries route to NAV and boost the canonical SLD."""

    def test_ebay_classifies_as_navigational(self):
        intent = classify("Ebay")
        assert intent.intent is Intent.NAVIGATIONAL
        assert intent.confidence >= 0.65

    def test_two_word_brand_classifies_as_navigational(self):
        # "Shake Shack" used to route ENTITY; now routes NAV.
        # Distinction was arbitrary.
        intent = classify("Shake Shack")
        assert intent.intent is Intent.NAVIGATIONAL

    def test_ebay_dot_com_promoted_to_first(self):
        """Canonical broken case: ebay.com last in original SERP, should be first."""
        intent = classify("Ebay")
        ranked = rerank(EBAY_SERP, intent)
        assert ranked[0]["url"] == "https://www.ebay.com/"

    def test_ebayinc_ranked_above_unrelated(self):
        """Corporate variant should rank well, just below the canonical."""
        intent = classify("Ebay")
        ranked = rerank(EBAY_SERP, intent)
        urls = [r["url"] for r in ranked]
        ebay_pos = next(i for i, u in enumerate(urls) if u == "https://www.ebay.com/")
        ebayinc_pos = next(i for i, u in enumerate(urls) if "ebayinc.com" in u)
        # ebay.com first, ebayinc.com near the top
        assert ebay_pos == 0
        assert ebayinc_pos <= 2

    def test_path_match_results_still_present(self):
        """instagram.com/ebay shouldn't be removed, just deprioritized."""
        intent = classify("Ebay")
        ranked = rerank(EBAY_SERP, intent)
        urls = [r["url"] for r in ranked]
        assert any("instagram.com" in u for u in urls)
        assert any("facebook.com" in u for u in urls)

    def test_entity_qualifier_blocks_strong_nav_boost(self):
        """'starbucks hours' is ENTITY (qualifier present); gets a modest boost,
        not the full NAV boost. starbucks.com still rises but is not pinned
        with the same dominance as a pure NAV query."""
        intent = classify("Starbucks hours")
        assert intent.intent is Intent.ENTITY
        results = [
            {"url": "https://example.com/article", "title": "r1", "description": "...", "quality_score": 0.7},
            {"url": "https://www.starbucks.com/", "title": "Starbucks", "description": "...", "quality_score": 0.5},
        ]
        ranked = rerank(results, intent)
        # ENTITY boost factor is 0.4 vs NAV's 1.0
        # starbucks.com gets boost = 1.0 * 2.5 * 0.4 = 1.0; total ~1.5
        # example.com stays at 0.7
        # so starbucks.com should be first, but boost is modest
        assert ranked[0]["url"] == "https://www.starbucks.com/"
        # And the boost is meaningfully smaller than the pure NAV case
        assert ranked[0]["rerank_score"] < 2.5


class TestNavReranker:
    def test_exact_sld_match_pins_to_first(self):
        intent = classify("OpenTable")
        results = [
            {"url": "https://news.com/opentable-acquired", "title": "OpenTable Acquired", "description": "...", "quality_score": 0.8},
            {"url": "https://wikipedia.org/wiki/OpenTable", "title": "OpenTable - Wikipedia", "description": "...", "quality_score": 0.7},
            {"url": "https://www.opentable.com/", "title": "OpenTable", "description": "Restaurant reservations.", "quality_score": 0.3},
        ]
        ranked = rerank_for_navigational_intent(results, intent)
        assert ranked[0]["url"] == "https://www.opentable.com/"

    def test_no_op_for_non_navigational_intent(self):
        intent = classify("palm springs restaurants")
        assert intent.intent is Intent.LIST
        results = EBAY_SERP
        ranked = rerank_for_navigational_intent(results, intent)
        # Returns input unchanged when intent isn't NAV
        assert [r["url"] for r in ranked] == [r["url"] for r in results]

    def test_short_query_does_not_match_short_substring(self):
        """Avoid false positives: 'AI' shouldn't match every domain with 'ai' in it."""
        intent = classify("AI")
        # Even if intent classifies somehow, the match scorer should be cautious
        # for very short queries (this is enforced by len(query_norm) < 2 check
        # and the >= 4 char threshold for substring matches).
        from backend.list_intent_reranker import _domain_match_score
        # "ai" is 2 chars; passes len >= 2 but substring match requires len >= 4
        assert _domain_match_score("https://stability.ai/", "ai") < 1.0
        assert _domain_match_score("https://openai.com/", "ai") == 0.0  # substring requires len >= 4

    def test_corporate_variant_lower_than_exact(self):
        from backend.list_intent_reranker import _domain_match_score
        exact = _domain_match_score("https://ebay.com/", "ebay")
        corp = _domain_match_score("https://ebayinc.com/", "ebay")
        assert exact > corp > 0

    def test_debug_features_attached(self):
        intent = classify("Ebay")
        ranked = rerank_for_navigational_intent(EBAY_SERP, intent, debug=True)
        for r in ranked:
            assert "rerank_score" in r
            assert "rerank_features" in r
            assert "domain_match_score" in r["rerank_features"]


class TestDispatchRerank:
    """The single-entry rerank() dispatches to the right reranker by intent."""

    def test_dispatches_list_intent(self):
        intent = classify("palm springs restaurants")
        ranked = rerank(SCREENSHOT_SERP, intent)
        # Should apply list reranking - Eater should rise above entity homepages
        urls = [r["url"] for r in ranked]
        eater_pos = next(i for i, u in enumerate(urls) if "eater.com" in u)
        farm_pos = next(i for i, u in enumerate(urls) if "farmpalmsprings" in u)
        assert eater_pos < farm_pos

    def test_dispatches_navigational_intent(self):
        intent = classify("Ebay")
        ranked = rerank(EBAY_SERP, intent)
        assert ranked[0]["url"] == "https://www.ebay.com/"

    def test_informational_no_domain_match_passes_order_through(self):
        """INFO intent with no domain matches: order is preserved, scores annotated."""
        intent = classify("how does dns work")
        results = [{"url": f"https://example{i}.com/", "title": f"r{i}", "description": "d", "quality_score": 0.5 - i*0.1} for i in range(3)]
        ranked = rerank(results, intent)
        # Same URLs in same order (no domain matched, no reordering)
        assert [r["url"] for r in ranked] == [r["url"] for r in results]

    def test_informational_with_domain_match_applies_modest_boost(self):
        """INFO intent with one result whose SLD matches the query word
        (lowercase brand case): modest boost lifts the match without pinning."""
        intent = classify("ebay")  # lowercase -> INFO
        assert intent.intent is Intent.INFORMATIONAL
        results = [
            {"url": "https://wikipedia.org/wiki/ebay", "title": "eBay - Wikipedia", "description": "...", "quality_score": 0.7},
            {"url": "https://www.ebay.com/", "title": "eBay", "description": "...", "quality_score": 0.3},
        ]
        ranked = rerank(results, intent)
        # ebay.com gets domain-match boost; lifts past Wikipedia
        assert ranked[0]["url"] == "https://www.ebay.com/"


# ----------------------------------------------------------------------
# Layer 6: Ambiguity detector tests
# ----------------------------------------------------------------------

class TestAmbiguityDetector:
    def test_concentrated_distribution_not_ambiguous(self):
        """All results in one bucket -> not ambiguous."""
        results = [{"url": f"https://example{i}.com/", "source_type": "Reference"} for i in range(8)]
        result = detect_ambiguity(results)
        assert not result.is_ambiguous

    def test_bimodal_distribution_flagged(self):
        """Two roughly-equal buckets -> ambiguous."""
        results = (
            [{"url": f"https://a{i}.com/", "source_type": "Commercial"} for i in range(5)]
            + [{"url": f"https://b{i}.com/", "source_type": "Reference"} for i in range(4)]
        )
        result = detect_ambiguity(results)
        assert result.is_ambiguous
        assert "Commercial" in result.emphasized_buckets
        assert "Reference" in result.emphasized_buckets

    def test_dominated_distribution_not_ambiguous(self):
        """9/1 split -> dominated, not ambiguous."""
        results = (
            [{"url": f"https://a{i}.com/", "source_type": "Commercial"} for i in range(9)]
            + [{"url": "https://b.com/", "source_type": "Reference"}]
        )
        result = detect_ambiguity(results)
        assert not result.is_ambiguous

    def test_multimodal_three_buckets(self):
        """4/3/3 distribution -> ambiguous, three buckets emphasized."""
        results = (
            [{"url": f"https://a{i}.com/", "source_type": "News"} for i in range(4)]
            + [{"url": f"https://b{i}.com/", "source_type": "Commercial"} for i in range(3)]
            + [{"url": f"https://c{i}.com/", "source_type": "Reference"} for i in range(3)]
        )
        result = detect_ambiguity(results)
        assert result.is_ambiguous
        assert len(result.emphasized_buckets) == 3

    def test_too_few_results(self):
        results = [
            {"url": "https://a.com/", "source_type": "News"},
            {"url": "https://b.com/", "source_type": "Reference"},
        ]
        result = detect_ambiguity(results)
        assert not result.is_ambiguous
        assert "too few" in result.explanation

    def test_other_bucket_ignored(self):
        """'Other' and unclassified shouldn't count as a real bucket."""
        results = (
            [{"url": f"https://a{i}.com/", "source_type": "Reference"} for i in range(6)]
            + [{"url": f"https://b{i}.com/", "source_type": "Other"} for i in range(6)]
        )
        result = detect_ambiguity(results)
        assert not result.is_ambiguous
        assert "Other" not in result.bucket_distribution

    def test_tide_genuinely_ambiguous(self):
        """4 ocean/wikipedia, 4 detergent commercial -> bimodal."""
        results = (
            [{"url": f"https://a{i}.com/", "source_type": "Reference"} for i in range(4)]
            + [{"url": f"https://b{i}.com/", "source_type": "Commercial"} for i in range(4)]
        )
        result = detect_ambiguity(results)
        assert result.is_ambiguous
        assert set(result.emphasized_buckets) == {"Reference", "Commercial"}


# ----------------------------------------------------------------------
# Lowercase brand integration (graded boost)
# ----------------------------------------------------------------------

class TestLowercaseBrandHandling:
    def test_lowercase_ebay_lifts_canonical_via_info_boost(self):
        """The majority case: user types 'ebay' lowercase. Classifier returns
        INFO. Graded boost still lifts ebay.com via INFO factor (0.3)."""
        intent = classify("ebay")
        assert intent.intent is Intent.INFORMATIONAL
        ranked = rerank(EBAY_SERP, intent)
        urls = [r["url"] for r in ranked]
        ebay_pos = urls.index("https://www.ebay.com/")
        assert ebay_pos <= 1, f"ebay.com at position {ebay_pos+1}, expected top 2"

    def test_lowercase_brand_boost_smaller_than_nav_boost(self):
        """INFO factor 0.3 produces a smaller boost than NAV factor 1.0."""
        nav_intent = classify("Ebay")
        info_intent = classify("ebay")
        nav_ranked = rerank(EBAY_SERP, nav_intent)
        info_ranked = rerank(EBAY_SERP, info_intent)
        nav_ebay = next(r for r in nav_ranked if r["url"] == "https://www.ebay.com/")
        info_ebay = next(r for r in info_ranked if r["url"] == "https://www.ebay.com/")
        assert nav_ebay["rerank_score"] > info_ebay["rerank_score"]

    def test_apple_lowercase_lifts_apple_com_modestly(self):
        """'apple' lowercase: INFO intent, modest boost lifts apple.com."""
        intent = classify("apple")
        assert intent.intent is Intent.INFORMATIONAL
        results = [
            {"url": "https://en.wikipedia.org/wiki/Apple", "title": "Apple - Wikipedia",
             "description": "...", "quality_score": 0.85, "source_type": "Reference"},
            {"url": "https://healthline.com/apples-nutrition", "title": "Apple nutrition",
             "description": "...", "quality_score": 0.75, "source_type": "Health"},
            {"url": "https://www.apple.com/", "title": "Apple", "description": "...",
             "quality_score": 0.40, "source_type": "Commercial"},
            {"url": "https://9to5mac.com/apple-news", "title": "Apple news",
             "description": "...", "quality_score": 0.65, "source_type": "News"},
        ]
        ranked = rerank(results, intent)
        # apple.com base 0.40 + boost (1.0 * 2.5 * 0.3) = 1.15 -> beats 0.85
        assert ranked[0]["url"] == "https://www.apple.com/"

    def test_starbucks_hours_strips_qualifier_before_match(self):
        """ENTITY query: 'starbucks hours' should match starbucks.com via
        qualifier stripping. Without that, 'starbuckshours' wouldn't match
        SLD 'starbucks'."""
        intent = classify("Starbucks hours")
        assert intent.intent is Intent.ENTITY
        results = [
            {"url": "https://yelp.com/biz/starbucks", "title": "Starbucks - Yelp",
             "description": "...", "quality_score": 0.75},
            {"url": "https://www.starbucks.com/", "title": "Starbucks",
             "description": "...", "quality_score": 0.4},
        ]
        ranked = rerank(results, intent)
        # ENTITY factor 0.4 * NAV_BOOST 2.5 * match_score 1.0 = 1.0 boost
        # starbucks.com: 0.4 + 1.0 = 1.4 ; yelp: 0.75
        assert ranked[0]["url"] == "https://www.starbucks.com/"
