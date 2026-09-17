"""Build a submission_rN.parquet from a downloaded traffic_rN.parquet.

Usage:
    python build_submission.py --bundle <bundle_dir> --traffic <traffic.parquet> \
        --out <submission.parquet> [--actions prior_actions1.parquet prior_actions2.parquet] \
        [--k 20] [--alpha 0.55] [--fit-weight 0.12]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ranker import load_bundle, rank_pair  # noqa: E402
from behavioral import Behavioral, load_actions  # noqa: E402


def build(bundle_dir: str, traffic_path: str, out_path: str,
          action_paths: list[str] | None, k: int = 20,
          top_k: int = 500, quality_weight: float = 0.2, rrf_k: float = 60.0,
          behavioral_weight: float = 0.3, fit_weight: float = 0.0) -> None:
    t0 = time.time()
    bundle = load_bundle(bundle_dir)
    print(f"[build_submission] bundle loaded in {time.time() - t0:.1f}s "
          f"({bundle.n_items} items)", file=sys.stderr)

    behavioral = None
    if action_paths:
        merged: dict[str, list] = {}
        for p in action_paths:
            rows = load_actions(p)
            for col, vals in rows.items():
                merged.setdefault(col, []).extend(vals)
        behavioral = Behavioral(bundle, merged)
        print(f"[build_submission] behavioral: global_ctr={behavioral.global_ctr:.4f} "
              f"users_with_brand_history={len(behavioral.clicked_brands)}", file=sys.stderr)

    traffic = pq.read_table(traffic_path).to_pydict()
    n_impressions = len(traffic["query_id"])
    seen_pairs: set[tuple[str, str]] = set()
    qids, uids = [], []
    for qid, uid in zip(traffic["query_id"], traffic["user_id"]):
        pair = (qid, uid)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            qids.append(qid)
            uids.append(uid)
    n_pairs = len(qids)
    print(f"[build_submission] traffic: {n_impressions} impressions, "
          f"{n_pairs} unique (query_id, user_id) pairs "
          f"({n_impressions - n_pairs} repeated impressions deduplicated)", file=sys.stderr)

    world_ids, query_ids, user_ids, ranks, item_ids = [], [], [], [], []
    world_id = traffic["world_id"][0]
    t1 = time.time()
    for i in range(n_pairs):
        qid, uid = qids[i], uids[i]
        top_items = rank_pair(bundle, qid, uid, k, top_k=top_k, quality_weight=quality_weight,
                               rrf_k=rrf_k, behavioral_weight=behavioral_weight,
                               fit_weight=fit_weight, behavioral=behavioral)
        world_ids.extend([world_id] * k)
        query_ids.extend([qid] * k)
        user_ids.extend([uid] * k)
        ranks.extend(range(k))
        item_ids.extend(top_items)
        if (i + 1) % 2000 == 0:
            elapsed = time.time() - t1
            print(f"[build_submission] ranked {i + 1}/{n_pairs} pairs "
                  f"({elapsed:.1f}s, {(i + 1) / elapsed:.0f}/s)", file=sys.stderr)

    table = pa.table({
        "world_id": world_ids,
        "query_id": query_ids,
        "user_id": user_ids,
        "rank": pa.array(ranks, type=pa.int32()),
        "item_id": item_ids,
    })
    pq.write_table(table, out_path)
    print(f"[build_submission] wrote {out_path} ({len(item_ids)} rows) "
          f"in {time.time() - t0:.1f}s total", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--traffic", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--actions", nargs="*", default=None)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--top-k", type=int, default=500)
    ap.add_argument("--quality-weight", type=float, default=0.2)
    ap.add_argument("--rrf-k", type=float, default=60.0)
    ap.add_argument("--behavioral-weight", type=float, default=0.3)
    ap.add_argument("--fit-weight", type=float, default=0.0)
    args = ap.parse_args()
    build(args.bundle, args.traffic, args.out, args.actions, args.k,
          args.top_k, args.quality_weight, args.rrf_k,
          args.behavioral_weight, args.fit_weight)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
