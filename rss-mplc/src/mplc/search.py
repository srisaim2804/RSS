"""Organic search index.

Backends, registered under the ``search_index`` plugin family:

* ``word_overlap`` — :class:`MockSearchIndex`, the default. Ranks by query/title
  token overlap (the monorepo's bm25s/tantivy/lancedb backends can be ported
  behind this same interface).
* ``bm25`` — :class:`BM25SearchIndex`. Same candidate set as ``word_overlap`` but
  orders it by the Okapi BM25 score (idf-weighted term matches + document-length
  normalisation) instead of the unweighted overlap fraction. Reported
  ``relevance`` stays pure token overlap — only the ordering changes.
* ``semantic`` — :class:`SemanticSearchIndex`. Re-ranks the lexical candidate set
  by a blend of token overlap and an LSA (TF-IDF + truncated SVD) cosine
  similarity, so titles that are *semantically* near the query can be promoted
  even when the literal overlap is weaker. The ``relevance`` value reported to
  the choice model stays pure token overlap — only the slot ordering changes,
  so the signal can't inflate its own downstream click probability.
* ``behavioral`` — :class:`ClickAwareSearchIndex`. Re-ranks the lexical candidate
  set by a blend of token overlap and a smoothed historical click-through rate
  (built offline from the correlated event log, e.g. ``experiments/_ab.build_ctr_stats``).
  Reported ``relevance`` again stays pure token overlap.
* ``blended`` — :class:`BlendedSearchIndex`. One tunable blend of all three
  (``w_overlap``/``w_semantic``/``w_ctr``); the other backends are its special
  cases. Personalization is layered on top of it in the marketplace.
"""
from __future__ import annotations

import json
import math

import numpy as np

from coms.infra import register

from .scoring import overlap


class MockSearchIndex:
    """Word-overlap retrieval over a product catalog. Satisfies coms SearchIndex."""

    def __init__(self) -> None:
        self._products: list = []

    def index(self, products) -> None:
        self._products = list(products)

    def search(self, query: str, k: int) -> list[dict]:
        scored = []
        for p in self._products:
            ov = overlap(query, p.title)
            if ov > 0:
                scored.append((ov, p))
        scored.sort(key=lambda x: (-x[0], x[1].product_id))
        return [{"product": p, "relevance": ov} for ov, p in scored[:k]]


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


class BM25SearchIndex:
    """Okapi BM25 ranker over product titles.

    Same candidate set as :class:`MockSearchIndex` (any title sharing >= 1 query
    token) but ordered by the BM25 score: rarer query terms (higher idf) and
    shorter titles (length normalisation) are rewarded, where plain overlap treats
    every matched token equally and divides by the query length. The ``relevance``
    reported for each hit is the pure ``overlap`` value, so only slot order changes.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._products: list = []
        self._k1, self._b = float(k1), float(b)
        self._tf: list[dict[str, int]] = []
        self._doc_len: list[int] = []
        self._idf: dict[str, float] = {}
        self._avgdl = 0.0

    def index(self, products) -> None:
        self._products = list(products)
        docs = [_tokenize(p.title) for p in self._products]
        n_docs = len(docs)
        self._doc_len = [len(d) for d in docs]
        self._avgdl = sum(self._doc_len) / n_docs if n_docs else 0.0
        self._tf, df = [], {}
        for d in docs:
            counts: dict[str, int] = {}
            for tok in d:
                counts[tok] = counts.get(tok, 0) + 1
            self._tf.append(counts)
            for tok in counts:
                df[tok] = df.get(tok, 0) + 1
        self._idf = {tok: math.log(1.0 + (n_docs - n + 0.5) / (n + 0.5))
                     for tok, n in df.items()}

    def _score(self, q_tokens: list[str], i: int) -> float:
        counts, dl = self._tf[i], self._doc_len[i]
        norm = (self._k1 * (1.0 - self._b + self._b * dl / self._avgdl)
                if self._avgdl else self._k1)
        s = 0.0
        for tok in q_tokens:
            f = counts.get(tok, 0)
            if f:
                s += self._idf.get(tok, 0.0) * f * (self._k1 + 1.0) / (f + norm)
        return s

    def search(self, query: str, k: int) -> list[dict]:
        if not self._products:
            return []
        q = _tokenize(query)
        scored = []
        for i, p in enumerate(self._products):
            ov = overlap(query, p.title)
            if ov <= 0:
                continue
            scored.append((self._score(q, i), ov, p))
        scored.sort(key=lambda x: (-x[0], x[2].product_id))
        return [{"product": p, "relevance": ov} for _, ov, p in scored[:k]]


class SemanticSearchIndex:
    """LSA semantic re-ranker over the product catalog.

    ``index`` builds a TF-IDF term-document matrix from product titles and reduces
    it with a truncated SVD to ``n_components`` latent dimensions. ``search`` keeps
    the same candidate set a word-overlap search would surface (overlap > 0) but
    orders it by ``(1 - sem_weight)·overlap + sem_weight·cosine`` where ``cosine``
    is the query/title similarity in the latent space. The ``relevance`` returned
    for each hit is the pure ``overlap`` value, never the cosine.
    """

    def __init__(self, n_components: int = 16, sem_weight: float = 0.5) -> None:
        self._products: list = []
        self._n_components = int(n_components)
        self._w = float(sem_weight)
        self._vocab: dict[str, int] = {}
        self._idf = np.zeros(0)
        self._components = np.zeros((0, 0))   # V_k : (k, |vocab|)
        self._doc_vecs = np.zeros((0, 0))     # (n_products, k), L2-normalized

    def index(self, products) -> None:
        self._products = list(products)
        docs = [_tokenize(p.title) for p in self._products]
        vocab = sorted({t for d in docs for t in d})
        self._vocab = {t: i for i, t in enumerate(vocab)}
        n_docs, n_terms = len(docs), len(vocab)
        if n_docs == 0 or n_terms == 0:
            self._components = np.zeros((0, 0))
            self._doc_vecs = np.zeros((0, 0))
            return
        tf = np.zeros((n_docs, n_terms))
        for i, d in enumerate(docs):
            for t in d:
                tf[i, self._vocab[t]] += 1.0
        df = (tf > 0).sum(axis=0)
        self._idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0
        tfidf = tf * self._idf
        tfidf = tfidf / np.clip(np.linalg.norm(tfidf, axis=1, keepdims=True), 1e-12, None)
        k = max(1, min(self._n_components, n_docs, n_terms))
        # truncated SVD:  tfidf ≈ U_k · diag(S_k) · V_k
        U, S, Vt = np.linalg.svd(tfidf, full_matrices=False)
        self._components = Vt[:k]                       # (k, n_terms)
        doc_vecs = U[:, :k] * S[:k]                     # (n_docs, k)
        self._doc_vecs = doc_vecs / np.clip(
            np.linalg.norm(doc_vecs, axis=1, keepdims=True), 1e-12, None)

    def _query_vec(self, query: str) -> np.ndarray:
        k = self._components.shape[0]
        v = np.zeros(len(self._vocab))
        for t in _tokenize(query):
            j = self._vocab.get(t)
            if j is not None:
                v[j] += 1.0
        n = np.linalg.norm(v * self._idf) if v.any() else 0.0
        if n < 1e-12:
            return np.zeros(k)
        q = self._components @ (v * self._idf / n)      # project into latent space
        qn = np.linalg.norm(q)
        return q / qn if qn > 1e-12 else q

    def cosine(self, query: str) -> dict[str, float]:
        """product_id → latent-space cosine similarity to the query, clipped to
        [0, 1]. Defined for every indexed product (0.0 when the query has no known
        terms). Used by :meth:`search` and by :class:`BlendedSearchIndex`."""
        if not self._products or self._doc_vecs.size == 0:
            return {}
        qv = self._query_vec(query)
        if not qv.any():
            return {p.product_id: 0.0 for p in self._products}
        return {p.product_id: max(0.0, float(qv @ self._doc_vecs[i]))
                for i, p in enumerate(self._products)}

    def search(self, query: str, k: int) -> list[dict]:
        if not self._products or self._doc_vecs.size == 0:
            return []
        cos = self.cosine(query)
        scored = []
        for p in self._products:
            ov = overlap(query, p.title)
            if ov <= 0:
                continue
            blended = (1.0 - self._w) * ov + self._w * cos.get(p.product_id, 0.0)
            scored.append((blended, ov, p))
        scored.sort(key=lambda x: (-x[0], x[2].product_id))
        return [{"product": p, "relevance": ov} for _, ov, p in scored[:k]]


def load_click_stats(path: str) -> dict:
    """Load a CTR-stats JSON (as written by ``experiments/_ab.build_ctr_stats``)."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {
        "global": float(raw.get("global", 0.0)),
        "item": {str(k): float(v) for k, v in raw.get("item", {}).items()},
        "query_item": {str(k): float(v) for k, v in raw.get("query_item", {}).items()},
    }


class ClickAwareSearchIndex:
    """Behavioural re-ranker over historical click-through rate.

    ``search`` scores each lexical candidate by
    ``(1 - ctr_weight)·overlap + ctr_weight·ctr_signal``, where ``ctr_signal`` is
    looked up ``(query, item)`` → ``item`` → global mean (the same fallback chain
    used when the stats were smoothed). This class is agnostic to how ``stats``
    was built; ``experiments/_ab.build_ctr_stats`` additively smooths raw
    click-through rate (organic impressions only) toward the global mean so a
    product with few impressions isn't penalised for one lucky/unlucky click.

    As with the other backends the ``relevance`` reported to the choice model is
    the pure ``overlap`` value: a historically well-clicked product is promoted to
    a better slot (higher ``p_seen``) but its ``p_click`` once seen is unchanged —
    the signal can't grade its own homework.
    """

    def __init__(self, ctr_weight: float = 0.5, stats: dict | None = None,
                 stats_path: str | None = None) -> None:
        self._products: list = []
        self._w = float(ctr_weight)
        if stats_path is not None:
            stats = load_click_stats(stats_path)
        s = stats or {}
        self._global = float(s.get("global", 0.0))
        self._item: dict[str, float] = dict(s.get("item", {}))
        self._qi: dict[str, float] = dict(s.get("query_item", {}))

    def index(self, products) -> None:
        self._products = list(products)

    def _ctr(self, query: str, pid: str) -> float:
        key = query.lower().strip() + "\t" + pid
        if key in self._qi:
            return self._qi[key]
        if pid in self._item:
            return self._item[pid]
        return self._global

    def search(self, query: str, k: int) -> list[dict]:
        scored = []
        for p in self._products:
            ov = overlap(query, p.title)
            if ov <= 0:
                continue
            sig = self._ctr(query, p.product_id)
            blended = (1.0 - self._w) * ov + self._w * sig
            scored.append((blended, ov, p))
        scored.sort(key=lambda x: (-x[0], x[2].product_id))
        return [{"product": p, "relevance": ov} for _, ov, p in scored[:k]]


class BlendedSearchIndex:
    """The full ranker: one tunable blend of every lexical/semantic/behavioural
    signal at once.

    ``sort key = (w_overlap·overlap + w_semantic·cosine + w_ctr·ctr) / Σw`` over the
    lexical candidate set (``overlap > 0``); reported ``relevance`` stays pure
    ``overlap``. Setting all weights but ``w_overlap`` to 0 reproduces
    ``word_overlap``; ``w_semantic``-only reproduces ``semantic``; ``w_ctr``-only
    reproduces ``behavioral``. Personalization is applied a layer up, in the
    marketplace, on top of whatever this returns.
    """

    def __init__(self, w_overlap: float = 1.0, w_semantic: float = 0.0,
                 w_ctr: float = 0.0, n_components: int = 16,
                 stats: dict | None = None, stats_path: str | None = None) -> None:
        self._products: list = []
        self._w_o = max(0.0, float(w_overlap))
        self._w_s = max(0.0, float(w_semantic))
        self._w_c = max(0.0, float(w_ctr))
        self._sem = SemanticSearchIndex(n_components=n_components) if self._w_s > 0 else None
        self._ctr = (ClickAwareSearchIndex(ctr_weight=1.0, stats=stats, stats_path=stats_path)
                     if self._w_c > 0 else None)

    def index(self, products) -> None:
        self._products = list(products)
        if self._sem is not None:
            self._sem.index(products)
        if self._ctr is not None:
            self._ctr.index(products)

    def search(self, query: str, k: int) -> list[dict]:
        if not self._products:
            return []
        denom = self._w_o + self._w_s + self._w_c or 1.0
        cos = self._sem.cosine(query) if self._sem is not None else {}
        scored = []
        for p in self._products:
            ov = overlap(query, p.title)
            if ov <= 0:
                continue
            c = cos.get(p.product_id, 0.0)
            b = self._ctr._ctr(query, p.product_id) if self._ctr is not None else 0.0
            key = (self._w_o * ov + self._w_s * c + self._w_c * b) / denom
            scored.append((key, ov, p))
        scored.sort(key=lambda x: (-x[0], x[2].product_id))
        return [{"product": p, "relevance": ov} for _, ov, p in scored[:k]]


def _mk_word_overlap(cfg: dict):
    return MockSearchIndex()


def _mk_blended(cfg: dict):
    return BlendedSearchIndex(
        w_overlap=cfg.get("w_overlap", 1.0), w_semantic=cfg.get("w_semantic", 0.0),
        w_ctr=cfg.get("w_ctr", 0.0), n_components=cfg.get("n_components", 16),
        stats=cfg.get("stats"), stats_path=cfg.get("stats_path"))


def _mk_bm25(cfg: dict):
    return BM25SearchIndex(k1=cfg.get("k1", 1.5), b=cfg.get("b", 0.75))


def _mk_semantic(cfg: dict):
    return SemanticSearchIndex(
        n_components=cfg.get("n_components", 16),
        sem_weight=cfg.get("sem_weight", 0.5))


def _mk_behavioral(cfg: dict):
    return ClickAwareSearchIndex(
        ctr_weight=cfg.get("ctr_weight", 0.5),
        stats=cfg.get("stats"), stats_path=cfg.get("stats_path"))


register("search_index", "word_overlap", _mk_word_overlap)
register("search_index", "bm25", _mk_bm25)
register("search_index", "semantic", _mk_semantic)
register("search_index", "behavioral", _mk_behavioral)
register("search_index", "blended", _mk_blended)
