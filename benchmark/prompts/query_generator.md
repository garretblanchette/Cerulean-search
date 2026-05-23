# Cerulean benchmark query generator

You are generating queries for the Cerulean benchmark suite. The benchmark tests whether the Cerulean source classifier produces appropriate role and type distributions for diverse user queries. Your job is to produce a query set that meaningfully exercises the classifier.

## Categories

Distribute queries roughly equally across these categories:

- **research**: Academic and library research queries. Things a researcher would type when looking for primary sources, peer-reviewed work, or scholarly analysis.
- **news**: Current events, breaking news, current affairs. Things a journalist or news consumer would type.
- **technical**: Programming, engineering, science problem-solving. Things a developer or technical professional would type.
- **commercial**: Shopping, product research, service comparison. Things a consumer evaluating a purchase would type.
- **controversial**: Political, contested, value-laden topics. Things where source role and type matter most for honest evaluation.

## Quality criteria

- **Realistic.** Queries should be plausibly typed by an actual user. No artificial constructions. Match the typing style real users would use (typos and casual phrasing are fine where appropriate).
- **Probative.** Each query should exercise a non-trivial classifier decision. Avoid trivially obvious queries ("Python documentation"). Prefer queries that expose decision boundaries: "when did the Roman Empire fall" tests role disambiguation between Wikipedia tertiary and academic secondary; "best vacuum cleaner" tests how commercial intent interacts with editorial review sites; "is fluoride safe" tests how the classifier handles contested topics where source type matters most.
- **Diverse.** Cover different intents, time horizons, levels of specificity, and topical domains within each category.
- **Edge cases.** Roughly 15% of queries should be genuinely hard: ambiguous intent, contested categorization, mixed-domain queries, queries that look one way but are really another.

## Output format

Return a single JSON array. Each entry:

```json
{
  "query": "<the query as a user would type it>",
  "category": "research | news | technical | commercial | controversial",
  "difficulty": "easy | medium | hard",
  "probes": "<one-sentence note on what classifier decision this query is meant to exercise>"
}
```

Difficulty distribution target: ~25% easy, ~60% medium, ~15% hard. Easy queries calibrate baseline accuracy; hard queries reveal classifier weaknesses; medium queries form the bulk of the signal.

## Task

Generate <<<N>>> queries.
