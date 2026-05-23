"""
Run the intent classifier against the labeled benchmark and print accuracy.

Usage: python -m backend.benchmark_intent

Treats 'ambiguous' labels as excluded from scoring. Counts category and
location detection independently of intent classification, so partial
failures are visible.

Exit code is non-zero if accuracy falls below a configured floor; this makes
the script CI-friendly. Tune ACCURACY_FLOOR as the benchmark set grows.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from backend.intent_classifier import classify


# Tune these as the benchmark grows
ACCURACY_FLOOR = 0.80   # overall intent classification floor
LIST_PRECISION_FLOOR = 0.90  # list precision matters most for the reranker


def run() -> int:
    bench_path = Path(__file__).parent / "intent_benchmark.json"
    data = json.loads(bench_path.read_text())
    queries = data["queries"]

    total = 0
    correct_intent = 0
    correct_category = 0
    category_attempts = 0
    correct_location = 0
    location_attempts = 0

    by_intent_total: dict[str, int] = defaultdict(int)
    by_intent_correct: dict[str, int] = defaultdict(int)

    # For LIST precision: of all queries we labeled LIST, how many did we get?
    # For LIST recall: of all queries the classifier called LIST, how many were actually LIST?
    list_tp = 0
    list_fp = 0
    list_fn = 0

    misclassifications: list[str] = []

    for entry in queries:
        if entry.get("intent") == "ambiguous":
            continue
        q = entry["q"]
        expected = entry["intent"]
        result = classify(q)
        predicted = result.intent.value

        total += 1
        by_intent_total[expected] += 1
        if predicted == expected:
            correct_intent += 1
            by_intent_correct[expected] += 1
        else:
            misclassifications.append(
                f"  {q!r:60} expected={expected:13} got={predicted} (conf={result.confidence:.2f})"
            )

        # LIST-specific precision/recall
        if expected == "list" and predicted == "list":
            list_tp += 1
        elif expected == "list" and predicted != "list":
            list_fn += 1
        elif expected != "list" and predicted == "list":
            list_fp += 1

        # Category detection
        if "category" in entry:
            expected_cat = entry["category"]
            category_attempts += 1
            if expected_cat is None:
                # Classifier may or may not detect; either is fine, don't score
                category_attempts -= 1
            elif result.category == expected_cat:
                correct_category += 1

        # Location detection (presence only, not exact string match)
        if "location_present" in entry:
            location_attempts += 1
            has_loc = result.location is not None
            if has_loc == entry["location_present"]:
                correct_location += 1

    # Print report
    print("=" * 70)
    print("Intent classifier benchmark")
    print("=" * 70)
    print(f"Total queries: {total}")
    print(f"Overall accuracy: {correct_intent}/{total} = {correct_intent/total:.1%}")
    print()
    print("By intent:")
    for intent in sorted(by_intent_total.keys()):
        c = by_intent_correct[intent]
        t = by_intent_total[intent]
        print(f"  {intent:15} {c}/{t}  ({c/t:.1%})")
    print()

    list_precision = list_tp / (list_tp + list_fp) if (list_tp + list_fp) else 0.0
    list_recall = list_tp / (list_tp + list_fn) if (list_tp + list_fn) else 0.0
    print(f"LIST precision: {list_precision:.1%}  (tp={list_tp}, fp={list_fp})")
    print(f"LIST recall:    {list_recall:.1%}  (tp={list_tp}, fn={list_fn})")

    if category_attempts:
        print(f"Category detection: {correct_category}/{category_attempts} ({correct_category/category_attempts:.1%})")
    if location_attempts:
        print(f"Location detection: {correct_location}/{location_attempts} ({correct_location/location_attempts:.1%})")

    if misclassifications:
        print()
        print("Misclassifications:")
        for m in misclassifications:
            print(m)

    print()
    accuracy = correct_intent / total
    if accuracy < ACCURACY_FLOOR:
        print(f"FAIL: accuracy {accuracy:.1%} below floor {ACCURACY_FLOOR:.1%}")
        return 1
    if list_precision < LIST_PRECISION_FLOOR:
        print(f"FAIL: list precision {list_precision:.1%} below floor {LIST_PRECISION_FLOOR:.1%}")
        return 1
    print(f"PASS: accuracy {accuracy:.1%}, list precision {list_precision:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
