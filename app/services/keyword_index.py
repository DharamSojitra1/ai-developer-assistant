"""In-memory BM25 keyword index for hybrid search.

Rebuilt from the vector collection whenever its contents change; fine for
collections of up to tens of thousands of chunks.
"""

import math
import re
from collections import Counter

TOKEN_PATTERN = re.compile(r"\w+(?:[.\-]\w+)*")

STOPWORDS = frozenset(
    """
    a an and are as at be but by can do does for from has have how i if in
    into is it its me my not of on or our so such that the their them then
    there these they this to was we were what when where which who why will
    with you your
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOPWORDS
    ]


class BM25Index:
    def __init__(
        self,
        ids: list[str],
        texts: list[str],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.ids = ids
        self.k1 = k1
        self.b = b
        self.term_counts = [Counter(tokenize(text)) for text in texts]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.average_length = (
            sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        )

        document_frequency: Counter[str] = Counter()

        for counts in self.term_counts:
            document_frequency.update(counts.keys())

        total = len(texts)
        self.idf = {
            term: math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def __len__(self) -> int:
        return len(self.ids)

    def scores(self, query: str) -> dict[str, float]:
        """BM25 score of every chunk that shares at least one query term."""
        terms = [term for term in set(tokenize(query)) if term in self.idf]

        if not terms or not self.average_length:
            return {}

        results = {}

        for chunk_id, counts, length in zip(
            self.ids,
            self.term_counts,
            self.lengths,
        ):
            score = 0.0

            for term in terms:
                frequency = counts.get(term)

                if not frequency:
                    continue

                normalization = self.k1 * (
                    1 - self.b + self.b * length / self.average_length
                )
                score += self.idf[term] * (
                    frequency * (self.k1 + 1) / (frequency + normalization)
                )

            if score > 0:
                results[chunk_id] = score

        return results


def reciprocal_rank_fusion(
    rankings: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """Merge ranked result lists by summing 1 / (k + rank) per chunk ID."""
    fused: dict[str, dict] = {}
    scores: dict[str, float] = {}

    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            chunk_id = result["id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank)
            # Earlier rankings (vector results) win on shared keys.
            fused[chunk_id] = {**result, **fused.get(chunk_id, {})}

    ordered = sorted(scores, key=scores.get, reverse=True)

    return [
        {**fused[chunk_id], "fusion_score": scores[chunk_id]}
        for chunk_id in ordered
    ]
