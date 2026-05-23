"""
Ambiguity detector (Layer 6 of the ranking refinement pipeline).

Analyzes the source-type distribution of returned results to detect when a
query is ambiguous in practice - meaning the result set splits across two or
more source-type buckets in non-trivial proportions.

The output is a hint, not a forced choice. The UI uses it to emphasize the
existing source-type filter chips so users can navigate the ambiguity if
they want, without imposing a choice on users who don't.

Why this lives at the result-set level rather than the query level:
    - "apple" the word is ambiguous in dictionary terms
    - "apple" the query is dominated by Apple Inc. in real-world search volume
    - The result set itself reveals which interpretations have web presence
    - Self-correcting as web content shifts; no curated ambiguity list to
      maintain

Pure function. No I/O. Sub-millisecond on realistic result-set sizes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ----------------------------------------------------------------------
# Tuning constants
# ----------------------------------------------------------------------

# A bucket is "significant" if it holds at least this share of the total.
_MIN_BUCKET_SHARE = 0.20

# A bucket is "comparable to the largest" if its count is within this
# ratio of the largest bucket's count. Higher = more lenient.
_MAX_RATIO_TO_LARGEST = 3.0

# Buckets to ignore when computing distribution - these don't represent
# meaningful disambiguation axes.
_IGNORED_BUCKETS = frozenset({"Other", "AI Content", None, ""})

# Minimum total results required for ambiguity detection to fire.
# Below this, the sample is too small to draw conclusions.
_MIN_TOTAL_RESULTS = 5


# ----------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------

@dataclass
class AmbiguityResult:
    """
    Output of detect_ambiguity. Carries enough information for both
    UI rendering and debugging.
    """
    is_ambiguous: bool
    bucket_distribution: dict[str, int] = field(default_factory=dict)
    emphasized_buckets: list[str] = field(default_factory=list)
    total_classified: int = 0
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "is_ambiguous": self.is_ambiguous,
            "bucket_distribution": self.bucket_distribution,
            "emphasized_buckets": self.emphasized_buckets,
            "total_classified": self.total_classified,
            "explanation": self.explanation,
        }


# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------

def detect_ambiguity(
    results: list[dict[str, Any]],
    *,
    source_type_field: str = "source_type",
    min_bucket_share: float = _MIN_BUCKET_SHARE,
    max_ratio_to_largest: float = _MAX_RATIO_TO_LARGEST,
) -> AmbiguityResult:
    """
    Analyze the source-type distribution of a result set.

    Args:
        results: List of search-result dicts. Each should have a source-type
            field (default key 'source_type'). Buckets in _IGNORED_BUCKETS
            are excluded from analysis.
        source_type_field: Name of the field containing the source-type
            bucket. Cerulean's existing classifier sets this; map the field
            name at the integration layer if needed.
        min_bucket_share: Minimum share of total results a bucket must hold
            to be considered significant.
        max_ratio_to_largest: Maximum ratio between a bucket's count and the
            largest bucket's count for the bucket to be considered comparable.

    Returns:
        AmbiguityResult with is_ambiguous=True if at least two buckets pass
        both thresholds.
    """
    # Tally buckets (excluding ignored values)
    distribution: dict[str, int] = {}
    for r in results:
        bucket = r.get(source_type_field)
        if bucket in _IGNORED_BUCKETS:
            continue
        if not isinstance(bucket, str):
            continue
        distribution[bucket] = distribution.get(bucket, 0) + 1

    total = sum(distribution.values())

    if total < _MIN_TOTAL_RESULTS:
        return AmbiguityResult(
            is_ambiguous=False,
            bucket_distribution=distribution,
            total_classified=total,
            explanation=f"too few classified results ({total} < {_MIN_TOTAL_RESULTS})",
        )

    if len(distribution) < 2:
        return AmbiguityResult(
            is_ambiguous=False,
            bucket_distribution=distribution,
            total_classified=total,
            explanation="only one significant bucket present",
        )

    # Identify the largest bucket
    largest_count = max(distribution.values())

    # A bucket is "significant" if it passes both thresholds
    significant: list[tuple[str, int]] = []
    for bucket, count in distribution.items():
        share = count / total
        ratio_to_largest = largest_count / count if count > 0 else float("inf")
        if share >= min_bucket_share and ratio_to_largest <= max_ratio_to_largest:
            significant.append((bucket, count))

    if len(significant) < 2:
        return AmbiguityResult(
            is_ambiguous=False,
            bucket_distribution=distribution,
            total_classified=total,
            explanation=(
                f"largest bucket {largest_count}/{total} dominates; "
                f"no other bucket above {min_bucket_share:.0%} share "
                f"and within {max_ratio_to_largest:.1f}x of largest"
            ),
        )

    # Sort emphasized buckets by count (descending), then alphabetically
    significant.sort(key=lambda t: (-t[1], t[0]))
    emphasized = [bucket for bucket, _ in significant]

    return AmbiguityResult(
        is_ambiguous=True,
        bucket_distribution=distribution,
        emphasized_buckets=emphasized,
        total_classified=total,
        explanation=(
            f"results split across {len(significant)} buckets: "
            + ", ".join(f"{b}={c}" for b, c in significant)
        ),
    )
