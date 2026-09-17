"""
TF-IDF category matching for knowledge updates.

Uses TF-IDF cosine similarity plus prefix-aware token matching and
n-gram Jaccard to catch truncated/misspelled category names.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Tuple

_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "it",
    "its", "not", "no", "nor", "so", "if", "then", "than", "as",
})


def tokenize(text: str) -> List[str]:
    text = text.lower().replace("_", " ")
    return [t for t in re.findall(r"[a-z0-9]+", text) if t not in _STOP_WORDS and len(t) > 1]


def _jaccard(a: str, b: str, n=2) -> float:
    sa, sb = _grams(a, n), _grams(b, n)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _grams(s: str, n: int) -> set:
    return {s[i:i+n] for i in range(max(0, len(s) - n + 1))}


class TfidfMatcher:
    def __init__(self, categories: List[str], sensitivity: float = 0.4):
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self._idf: Dict[str, float] = {}
        self._build_idf(categories)

    def _build_idf(self, categories: List[str]):
        n = len(categories) or 1
        df: Counter = Counter()
        for cat in categories:
            for tok in set(tokenize(cat)):
                df[tok] += 1
        self._idf = {t: math.log(n / (c + 1)) + 1 for t, c in df.items()}

    @staticmethod
    def _tf_vec(tokens: List[str]) -> Dict[str, float]:
        counts = Counter(tokens)
        total = len(tokens) or 1
        return {t: c / total for t, c in counts.items()}

    @staticmethod
    def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
        inter = {k: a[k] * b[k] for k in a if k in b}
        if not inter:
            return 0.0
        dot = sum(inter.values())
        la = math.sqrt(sum(v * v for v in a.values())) or 1.0
        lb = math.sqrt(sum(v * v for v in b.values())) or 1.0
        return dot / (la * lb)

    @staticmethod
    def _prefix_match(cand_tokens: List[str], cat_tokens: List[str]) -> float:
        """Score based on how many candidate tokens are prefixes of (or contained in) category tokens."""
        if not cand_tokens:
            return 0.0
        hits = 0
        for ct in cand_tokens:
            for tt in cat_tokens:
                if ct in tt or tt in ct:
                    hits += 1; break
        return hits / len(cand_tokens)

    def match_category(self, candidate: str, categories: List[str]) -> Tuple[str, float]:
        cand_tokens = tokenize(candidate)
        cand_vec = self._tf_vec(cand_tokens)
        best_cat, best_score = "", 0.0
        for cat in categories:
            cat_tokens = tokenize(cat)
            tfidf_score = self._cosine(cand_vec, self._tf_vec(cat_tokens))
            ngram_score = max(_jaccard(candidate, cat, n) for n in (2, 3))
            prefix_score = self._prefix_match(cand_tokens, cat_tokens)
            score = 0.3 * tfidf_score + 0.25 * ngram_score + 0.45 * prefix_score
            if score > best_score:
                best_score = score
                best_cat = cat
        return best_cat, best_score

    def is_match(self, candidate: str, categories: List[str]) -> Tuple[bool, str, float]:
        cat, score = self.match_category(candidate, categories)
        return (score >= self.sensitivity), cat, score


def match_category(candidate: str, categories: List[str],
                   sensitivity: float = 0.4) -> Tuple[bool, str, float]:
    m = TfidfMatcher(categories, sensitivity)
    return m.is_match(candidate, categories)
