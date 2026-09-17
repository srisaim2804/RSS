"""Ranker for the ire-a2-tester assignment.

Builds a slate of `slate_size` item_ids per (query_id, user_id) pair, using only
data the bundle actually exposes (no oracle/relevance/latent columns exist here —
the tester image's schemas.json explicitly forbids them).

Design, in three layers that stack round over round as behavioral data accrues:

1. Content score (round 1 onward): 3-way Reciprocal Rank Fusion over BM25 (lexical),
   cosine similarity over the published sentence-transformer embeddings (semantic),
   and a static quality score (rating adjusted for price). Fusing at the rank level
   (`1/(k+rank)` per channel, k=60) rather than blending raw scores avoids having to
   pick a relative weighting between two differently-scaled signals (BM25 scores and
   cosine similarities don't live on comparable scales) — this measurably beat a plain
   linear BM25/semantic blend on real round-1 data (+2.6% relative expected value in
   a same-world comparison run), so it replaced the earlier linear-blend approach here.
2. Fit score: a per-user adjustment using the two numeric user features with an
   unambiguous, documented-by-naming-convention sign — price_sensitivity (prefer
   cheaper) and review_dependency (prefer higher-rated) — against catalogue
   price/rating z-scores. DEFAULT WEIGHT IS 0.0 as of round 1's real result: a
   same-world A/B on the actual simulator showed this "nudge" changed the #1
   item for 58% of pairs (RRF's rank-gaps near the slate cutoff are tiny, so even
   a small additive term dominates there) and cost real score — 0.0663 EV with
   it on vs. 0.0722 without, a ~9% relative drop, below even the plain BM25
   baseline. Left in the code (not deleted) since the mechanism itself may still
   be useful at a much smaller weight or combined with validated behavioral
   signal, but it must not ship enabled without re-testing on real traffic.
3. Behavioral score (round 2+): once we have a prior round's actions log, we can
   estimate a real per-item and per-brand click signal, inverse-propensity
   weighted since the log is confounded by slot position and the exploration
   policy's own propensity (per the assignment brief: "actions are not
   ground-truth relevance"). Also unlocks a brand-affinity term: a small bonus for
   brands a user has already clicked, standing in for brand_loyalty now that we
   have a user-specific, non-guessed way to apply it.

Fit and behavioral stay small additive nudges on top of the RRF base score (see the
weight defaults in `rank_pair`) — RRF scores for a top-ranked, dual-channel candidate
sit in the ~0.02-0.05 range, so the nudge weights are scaled down from their old
linear-blend values to keep them nudges rather than lets them dominate the ranking.
"""
from __future__ import annotations

import pickle
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

_STUDENT_MARKERS = ("rss-usim/src", "rss-coms/src", "rss-mplc/src")


def _bm25_index_from_pickle(path: Path, bm25_module):
    with path.open("rb") as fh:
        payload = pickle.load(fh)
    index = bm25_module.Bm25Index.__new__(bm25_module.Bm25Index)
    index.k1 = float(payload["k1"])
    index.b = float(payload["b"])
    index.n_docs = int(payload["n_docs"])
    index.lengths = np.asarray(payload["lengths"], dtype=np.float64)
    index.avg_length = float(payload["avg_length"])
    index._postings = payload["postings"]
    index._idf = payload["idf"]
    return index


def _load_student_bm25(bundle_dir: Path):
    student_dir = str(bundle_dir / "student")
    if student_dir not in sys.path:
        sys.path.insert(0, student_dir)
    import bm25 as bm25_module  # the vendored, dependency-free module
    return bm25_module


@dataclass
class Bundle:
    bundle_dir: Path
    schemas: dict
    catalogue: dict  # column -> list, includes 'embedding'
    users: dict
    queries: dict
    query_embeddings: dict

    item_ids: np.ndarray = field(init=False)
    item_vecs: np.ndarray = field(init=False)      # (n_items, dim), L2-normalized
    item_price: np.ndarray = field(init=False)
    item_rating: np.ndarray = field(init=False)
    item_brand: np.ndarray = field(init=False)
    bm25 = None  # Bm25Index

    query_text_by_id: dict = field(init=False)
    query_vec_by_id: dict = field(init=False)

    user_by_id: dict = field(init=False)

    def __post_init__(self):
        self.item_ids = np.asarray(self.catalogue["item_id"])
        vecs = np.asarray(self.catalogue["embedding"], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        self.item_vecs = vecs / np.clip(norms, 1e-8, None)
        self.item_price = np.asarray(self.catalogue["price"], dtype=np.float64)
        self.item_rating = np.asarray(self.catalogue["rating"], dtype=np.float64)
        self.item_brand = np.asarray(self.catalogue["brand"])

        self._price_mean, self._price_std = self.item_price.mean(), self.item_price.std() or 1.0
        self._rating_mean, self._rating_std = self.item_rating.mean(), self.item_rating.std() or 1.0

        # Static quality score: rating in [0,1], damped by a log penalty once price
        # exceeds 100 (a moderate reasonableness check, not a hard cutoff).
        norm_rating = np.clip(self.item_rating / 5.0, 0.0, 1.0)
        price_factor = 1.0 / (1.0 + np.log1p(np.maximum(0.0, self.item_price - 100.0) / 100.0))
        self.quality_score = norm_rating * price_factor

        self.query_text_by_id = dict(zip(self.queries["query_id"], self.queries["text"]))
        qvecs = np.asarray(self.query_embeddings["embedding"], dtype=np.float32)
        qvecs = qvecs / np.clip(np.linalg.norm(qvecs, axis=1, keepdims=True), 1e-8, None)
        self.query_vec_by_id = dict(zip(self.query_embeddings["query_id"], qvecs))

        self.user_by_id = {
            uid: {k: self.users[k][i] for k in self.users if k != "world_id"}
            for i, uid in enumerate(self.users["user_id"])
        }

        self._item_index_by_id = {iid: i for i, iid in enumerate(self.item_ids)}

    @property
    def n_items(self) -> int:
        return len(self.item_ids)


def load_bundle(bundle_dir: str | Path) -> Bundle:
    bundle_dir = Path(bundle_dir)
    bm25_module = _load_student_bm25(bundle_dir)

    def load_parquet(name: str) -> dict:
        table = pq.read_table(str(bundle_dir / name))
        return {c: table.column(c).to_pylist() for c in table.column_names}

    import json
    schemas = json.loads((bundle_dir / "schemas.json").read_text(encoding="ascii"))
    catalogue = load_parquet("catalogue.parquet")
    users = load_parquet("users.parquet")
    queries = load_parquet("queries.parquet")
    query_embeddings = load_parquet("query_embeddings.parquet")

    bundle = Bundle(bundle_dir, schemas, catalogue, users, queries, query_embeddings)

    bm25_path = bundle_dir / schemas.get("bm25_index", "catalogue_bm25.pkl")
    bundle.bm25 = _bm25_index_from_pickle(bm25_path, bm25_module)
    return bundle


def _top_k_indices(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k largest entries, sorted descending."""
    if k >= scores.size:
        return np.argsort(scores)[::-1]
    top = np.argpartition(scores, -k)[-k:]
    return top[np.argsort(scores[top])[::-1]]


_RRF_CACHE: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def rrf_scores(bundle: Bundle, query_id: str, top_k: int = 500,
               quality_weight: float = 0.2, rrf_k: float = 60.0,
               behavioral_ctr: np.ndarray | None = None, behavioral_weight: float = 0.3,
               ) -> tuple[np.ndarray, np.ndarray]:
    """Reciprocal Rank Fusion over BM25, semantic, quality, and (optionally) a
    behavioral CTR channel.

    Retrieves the top `top_k` candidates from BM25 and from semantic cosine
    similarity independently, takes their union, and scores each candidate in
    that union by `sum(1 / (rrf_k + rank))` across whichever channels rank it —
    quality and behavioral are ranked only within the union, and their terms
    are scaled by their respective weights. Fusing at the rank level sidesteps
    having to pick a relative weight between signals on genuinely different
    scales (BM25 scores, cosine similarities, click-through rates).

    `behavioral_ctr` (whole-catalogue array, e.g. Behavioral.item_ctr) is
    deliberately folded in HERE as a ranked channel rather than added as a raw
    post-hoc score the way an earlier version of this ranker did both this and
    a user-fit adjustment: that raw-additive approach measurably hurt round-1's
    real score (see ranker.py module docstring and fit_adjustment) because RRF
    scores in the top-20 have very tight rank-gaps, so even a "small" raw
    weight ends up dominating instead of nudging. A rank-based channel doesn't
    have that failure mode — it's on the same footing as every other channel.

    Returns (candidate_indices, rrf_score) — NOT a dense per-item array, since
    the whole point is to only score the union, not all 100k items. Memoized
    per (bundle, query_id, top_k, quality_weight, rrf_k, id(behavioral_ctr),
    behavioral_weight) — behavioral_ctr is per-round (not per-user), so it's
    still just as cacheable per query as everything else here."""
    key = (id(bundle), query_id, top_k, quality_weight, rrf_k,
           id(behavioral_ctr), behavioral_weight)
    cached = _RRF_CACHE.get(key)
    if cached is not None:
        return cached

    text = bundle.query_text_by_id[query_id]
    bm25_raw = bundle.bm25.scores(text)
    bm25_top = _top_k_indices(bm25_raw, top_k)

    qvec = bundle.query_vec_by_id.get(query_id)
    if qvec is not None:
        cosine = bundle.item_vecs @ qvec
        sem_top = _top_k_indices(cosine, top_k)
    else:
        sem_top = np.array([], dtype=bm25_top.dtype)

    bm25_rank = {int(idx): r for r, idx in enumerate(bm25_top, start=1)}
    sem_rank = {int(idx): r for r, idx in enumerate(sem_top, start=1)}
    candidates = np.array(sorted(set(bm25_rank) | set(sem_rank)), dtype=np.int64)

    if candidates.size == 0:
        result = (candidates, np.zeros(0))
        _RRF_CACHE[key] = result
        return result

    quality_order = np.argsort(-bundle.quality_score[candidates])
    quality_rank = {int(candidates[pos]): r for r, pos in enumerate(quality_order, start=1)}

    behavioral_rank = None
    if behavioral_ctr is not None:
        beh_order = np.argsort(-behavioral_ctr[candidates])
        behavioral_rank = {int(candidates[pos]): r for r, pos in enumerate(beh_order, start=1)}

    score = np.zeros(candidates.size)
    for i, idx in enumerate(candidates):
        idx = int(idx)
        s = 0.0
        if idx in bm25_rank:
            s += 1.0 / (rrf_k + bm25_rank[idx])
        if idx in sem_rank:
            s += 1.0 / (rrf_k + sem_rank[idx])
        s += quality_weight / (rrf_k + quality_rank[idx])
        if behavioral_rank is not None:
            s += behavioral_weight / (rrf_k + behavioral_rank[idx])
        score[i] = s

    result = (candidates, score)
    _RRF_CACHE[key] = result
    return result


_FIT_CACHE: dict[tuple[int, str, float], np.ndarray] = {}


def fit_adjustment(bundle: Bundle, user_id: str, weight: float = 0.12) -> np.ndarray:
    """(n_items,) small +/- adjustment from the two features with an unambiguous
    sign: price_sensitivity (higher -> prefer cheaper) and review_dependency
    (higher -> prefer higher-rated). Both z-scored against the full catalogue.
    Memoized per (bundle, user_id, weight) — depends only on the user, not the
    query, and there are only 400 users versus up to 14.4k pairs per round."""
    key = (id(bundle), user_id, weight)
    cached = _FIT_CACHE.get(key)
    if cached is not None:
        return cached
    user = bundle.user_by_id[user_id]
    price_z = (bundle.item_price - bundle._price_mean) / bundle._price_std
    rating_z = (bundle.item_rating - bundle._rating_mean) / bundle._rating_std
    price_term = -float(user["price_sensitivity"]) * price_z
    rating_term = float(user["review_dependency"]) * rating_z
    raw = 0.5 * price_term + 0.5 * rating_term
    # squash to a bounded +/- band so it nudges, never dominates, the content score
    result = weight * np.tanh(raw / 3.0)
    _FIT_CACHE[key] = result
    return result


def rank_pair(bundle: Bundle, query_id: str, user_id: str, k: int,
              top_k: int = 500, quality_weight: float = 0.2, rrf_k: float = 60.0,
              behavioral_weight: float = 0.3,
              fit_weight: float = 0.0, behavioral=None) -> list[str]:
    """Return the top-k item_ids for one (query_id, user_id) pair.

    Behavioral CTR (when `behavioral` is given) is folded into the RRF fusion
    itself as another ranked channel — see `rrf_scores` — not added as a raw
    post-hoc score. `fit_weight` defaults to 0 and is a raw additive nudge
    left over from before that lesson (see its docstring); pass it explicitly
    only after re-validating on real traffic, not by default. Per-user brand
    affinity (`behavioral.adjustment`'s other term) is not applied here for
    the same reason and isn't easily rank-fusable per-query, so it's dropped
    from this round's ranker rather than re-introduced as another raw nudge."""
    behavioral_ctr = behavioral.item_ctr if behavioral is not None else None
    candidates, score = rrf_scores(bundle, query_id, top_k=top_k,
                                    quality_weight=quality_weight, rrf_k=rrf_k,
                                    behavioral_ctr=behavioral_ctr,
                                    behavioral_weight=behavioral_weight)
    if candidates.size == 0:
        return []
    if fit_weight:
        score = score + fit_adjustment(bundle, user_id, weight=fit_weight)[candidates]

    n = min(k, candidates.size)
    top = _top_k_indices(score, n)
    return [str(bundle.item_ids[candidates[i]]) for i in top]
