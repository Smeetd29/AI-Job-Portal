from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[./-][a-z0-9]+)*[+#]*", re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


class BM25Index:
    """Small-corpus BM25 ranker for reproducible offline retrieval experiments."""

    def __init__(
        self,
        document_ids: Sequence[str],
        documents: Sequence[str],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if len(document_ids) != len(documents):
            raise ValueError("document_ids and documents must have equal lengths.")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and b between 0 and 1.")
        if len(set(document_ids)) != len(document_ids):
            raise ValueError("BM25 document IDs must be unique.")

        self.document_ids = list(document_ids)
        self.k1 = k1
        self.b = b
        self._term_frequencies = [Counter(tokenize(document)) for document in documents]
        self._lengths = [sum(frequencies.values()) for frequencies in self._term_frequencies]
        self._average_length = (
            sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        )
        document_frequency: Counter[str] = Counter()
        for frequencies in self._term_frequencies:
            document_frequency.update(frequencies.keys())
        self._inverse_document_frequency = {
            term: math.log1p(
                (len(self.document_ids) - frequency + 0.5) / (frequency + 0.5)
            )
            for term, frequency in document_frequency.items()
        }

    def score(self, query: str) -> Dict[str, float]:
        query_terms = tokenize(query)
        scores = {document_id: 0.0 for document_id in self.document_ids}
        if not query_terms or not self.document_ids:
            return scores
        for document_id, frequencies, length in zip(
            self.document_ids, self._term_frequencies, self._lengths
        ):
            normalization = self.k1 * (
                1.0 - self.b
                + self.b * length / self._average_length
            ) if self._average_length else self.k1
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                idf = self._inverse_document_frequency[term]
                scores[document_id] += (
                    idf
                    * frequency
                    * (self.k1 + 1.0)
                    / (frequency + normalization)
                )
        return scores

    def rank(self, query: str) -> List[str]:
        scores = self.score(query)
        return sorted(self.document_ids, key=lambda item: (-scores[item], item))


def reciprocal_rank_fusion(
    rankings: Iterable[Sequence[str]],
    rank_constant: int = 60,
) -> List[str]:
    if rank_constant < 0:
        raise ValueError("rank_constant must be non-negative.")
    scores: Dict[str, float] = {}
    first_seen: Dict[str, int] = {}
    encounter_index = 0
    for ranking in rankings:
        seen_in_ranking = set()
        for rank, document_id in enumerate(ranking, start=1):
            if document_id in seen_in_ranking:
                continue
            seen_in_ranking.add(document_id)
            first_seen.setdefault(document_id, encounter_index)
            encounter_index += 1
            scores[document_id] = scores.get(document_id, 0.0) + (
                1.0 / (rank_constant + rank)
            )
    return sorted(
        scores,
        key=lambda item: (-scores[item], first_seen[item], item),
    )
