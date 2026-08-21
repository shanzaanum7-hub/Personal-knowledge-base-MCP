"""Benchmark retrieval quality using Hit Rate and Mean Reciprocal Rank.

Dataset format (JSON or JSONL):
`{"query": "...", "expected_documents": ["doc-1", "doc-2"]}`.
The search adapter must return ranked document IDs, or mappings containing a
`doc_id` field. It receives no user ID: production adapters should obtain that
value from the authenticated request context.
"""

import argparse
import importlib
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """Load benchmark records from a JSON array or newline-delimited JSON."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    data = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines()]
    if not isinstance(data, list):
        raise ValueError("Benchmark dataset must be a JSON array or JSONL file")
    return data


def _document_id(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping) and isinstance(result.get("doc_id"), str):
        return result["doc_id"]
    raise ValueError("Search results must be document IDs or mappings with doc_id")


def run_benchmark(
    records: Iterable[Mapping[str, Any]],
    search: Callable[[str], Iterable[Any]],
    top_k: int = 10,
) -> dict[str, float | int]:
    """Run retrieval queries and return Hit Rate, MRR, and query count."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    total = hits = 0
    reciprocal_rank_sum = 0.0
    for record in records:
        query = record.get("query")
        expected = record.get("expected_documents")
        if not isinstance(query, str) or not isinstance(expected, list):
            raise ValueError("Each record needs query and expected_documents fields")
        expected_ids = {item for item in expected if isinstance(item, str)}
        ranked_ids = [_document_id(result) for result in search(query)][:top_k]
        rank = next((index for index, doc_id in enumerate(ranked_ids, 1) if doc_id in expected_ids), None)
        total += 1
        if rank is not None:
            hits += 1
            reciprocal_rank_sum += 1 / rank
    return {
        "queries": total,
        "hit_rate": hits / total if total else 0.0,
        "mrr": reciprocal_rank_sum / total if total else 0.0,
    }


def _load_callable(reference: str) -> Callable[[str], Iterable[Any]]:
    module_name, separator, function_name = reference.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("Search adapter must use module:function format")
    function = getattr(importlib.import_module(module_name), function_name)
    if not callable(function):
        raise TypeError(f"Search adapter is not callable: {reference}")
    return function


def main() -> None:
    """Parse CLI arguments, run the adapter, and print JSON metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--search", required=True, help="Search adapter as module:function")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(load_dataset(args.dataset), _load_callable(args.search), args.top_k), indent=2))


if __name__ == "__main__":
    main()