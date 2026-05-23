#!/usr/bin/env python3
"""Cerulean benchmark labeler runner.

Reads a query set, calls an LLM API to label each query against the
methodology criteria, writes a labels file.

Env vars (set in .env or shell):
  BENCHMARK_LABELER_API_KEY  - API key (Gemini, from https://aistudio.google.com/apikey)
  BENCHMARK_LABELER_MODEL    - model name (default: gemini-3.1-pro)

Usage:
  python benchmark/label_runner.py \
    --queries benchmark/queries_smoke.json \
    --output benchmark/labels_smoke.json

  python benchmark/label_runner.py \
    --queries benchmark/queries_smoke.json \
    --output benchmark/labels_smoke.json \
    --max 5    # process only the first 5 queries (smoke-test the runner itself)
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types

PROMPT_PATH = Path(__file__).parent / "prompts" / "labeler.md"
DEFAULT_MODEL = "gemini-3.1-pro"
SLEEP_BETWEEN_CALLS_SEC = 4  # Conservative for free-tier rate limits


def load_prompt() -> str:
    return PROMPT_PATH.read_text()


def label_query(client, model_name: str, prompt_template: str, query: str) -> dict:
    prompt = prompt_template.replace("<<<QUERY>>>", query)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True, help="Path to queries JSON file")
    parser.add_argument("--output", required=True, help="Path to output labels JSON file")
    parser.add_argument("--max", type=int, default=None, help="Limit to first N queries")
    parser.add_argument("--sleep", type=float, default=SLEEP_BETWEEN_CALLS_SEC,
                        help=f"Seconds between API calls (default {SLEEP_BETWEEN_CALLS_SEC})")
    args = parser.parse_args()

    api_key = os.environ.get("BENCHMARK_LABELER_API_KEY")
    model_name = os.environ.get("BENCHMARK_LABELER_MODEL", DEFAULT_MODEL)
    if not api_key:
        sys.exit("BENCHMARK_LABELER_API_KEY not set (export it or put it in .env at repo root)")

    print(f"Model: {model_name}")
    print(f"Sleep: {args.sleep}s between calls")

    client = genai.Client(api_key=api_key)
    queries = json.loads(Path(args.queries).read_text())
    if args.max:
        queries = queries[: args.max]
    print(f"Queries: {len(queries)}")

    prompt_template = load_prompt()
    labels = []
    errors = 0
    for i, q in enumerate(queries):
        query_text = q["query"]
        print(f"[{i+1}/{len(queries)}] {query_text}")
        try:
            label = label_query(client, model_name, prompt_template, query_text)
            labels.append({"input": q, "label": label})
        except Exception as e:
            print(f"  ERROR: {e}")
            labels.append({"input": q, "error": str(e)})
            errors += 1
        # Save partial results every 10 queries so a crash doesn't lose everything
        if (i + 1) % 10 == 0:
            Path(args.output).write_text(json.dumps(labels, indent=2))
        if i < len(queries) - 1:
            time.sleep(args.sleep)

    Path(args.output).write_text(json.dumps(labels, indent=2))
    print(f"\nWrote {len(labels)} entries to {args.output} ({errors} errors)")


if __name__ == "__main__":
    main()
