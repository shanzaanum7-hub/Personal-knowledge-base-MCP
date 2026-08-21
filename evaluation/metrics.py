"""Ranking metrics for evaluating semantic retrieval quality."""

from collections.abc import Iterable, Sequence


def _validate_inputs(retrieved: Sequence[str], expected: set[str], top_k: int) -> None:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if not expected:
        raise ValueError("expected document IDs must not be empty")
    if any(not isinstance(document_id, str) for document_id in retrieved):
        raise TypeError("retrieved document IDs must be strings")


def hit_rate(retrieved: Iterable[str], expected: Iterable[str], top_k: int = 10) -> float:
    """Return 1.0 when at least one expected document is retrieved in top-k."""
    retrieved_ids = list(retrieved)[:top_k]
    expected_ids = set(expected)
    _validate_inputs(retrieved_ids, expected_ids, top_k)
    return float(bool(set(retrieved_ids) & expected_ids))


def reciprocal_rank(retrieved: Iterable[str], expected: Iterable[str], top_k: int = 10) -> float:
    """Return the reciprocal rank of the first expected document, or zero."""
    retrieved_ids = list(retrieved)[:top_k]
    expected_ids = set(expected)
    _validate_inputs(retrieved_ids, expected_ids, top_k)
    for rank, document_id in enumerate(retrieved_ids, start=1):
        if document_id in expected_ids:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved: Iterable[str], expected: Iterable[str], top_k: int = 10) -> float:
    """Return the fraction of the top-k results that are relevant."""
    retrieved_ids = list(retrieved)[:top_k]
    expected_ids = set(expected)
    _validate_inputs(retrieved_ids, expected_ids, top_k)
    return sum(document_id in expected_ids for document_id in retrieved_ids) / top_k


def recall_at_k(retrieved: Iterable[str], expected: Iterable[str], top_k: int = 10) -> float:
    """Return the fraction of expected documents found in the top-k results."""
    retrieved_ids = list(retrieved)[:top_k]
    expected_ids = set(expected)
    _validate_inputs(retrieved_ids, expected_ids, top_k)
    return len(set(retrieved_ids) & expected_ids) / len(expected_ids)


def evaluate_retrieval(
    queries: Iterable[tuple[Iterable[str], Iterable[str]]], top_k: int = 10
) -> dict[str, float | int]:
    """Calculate aggregate Hit Rate, MRR, Precision, and Recall.

    Each query is a ``(retrieved_ids, expected_ids)`` pair. Results are macro
    averages, giving every query equal weight.
    """
    query_pairs = list(queries)
    if not query_pairs:
        return {"queries": 0, "hit_rate": 0.0, "mrr": 0.0, "precision": 0.0, "recall": 0.0}
    scores = [
        (
            hit_rate(retrieved, expected, top_k),
            reciprocal_rank(retrieved, expected, top_k),
            precision_at_k(retrieved, expected, top_k),
            recall_at_k(retrieved, expected, top_k),
        )
        for retrieved, expected in query_pairs
    ]
    count = len(scores)
    return {
        "queries": count,
        "hit_rate": sum(score[0] for score in scores) / count,
        "mrr": sum(score[1] for score in scores) / count,
        "precision": sum(score[2] for score in scores) / count,
        "recall": sum(score[3] for score in scores) / count,
    }