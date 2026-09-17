"""Submit one round's submission parquet, then fetch actions + round report.

Usage:
    python submit_round.py --base http://127.0.0.1:8000 --session <sid> --round <n> \
        --submission work/submission_rN.parquet \
        --actions-out work/actions_rN.parquet --report-out work/report_rN.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_client import TesterClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--session", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--actions-out", required=True)
    ap.add_argument("--report-out", required=True)
    ap.add_argument("--timeout", type=float, default=86400.0)
    args = ap.parse_args()

    client = TesterClient(args.base, timeout=args.timeout)

    t0 = time.time()
    print(f"[submit_round] submitting round {args.round} ...", file=sys.stderr)
    result = client.submit(args.session, args.round, args.submission)
    elapsed = time.time() - t0
    print(f"[submit_round] submit responded in {elapsed:.1f}s", file=sys.stderr)

    # The submission response already carries score/baselines/actions/coverage —
    # save it in full immediately. Don't rely on it only surviving inside a
    # variable: the separate GET /report call has been observed to hang
    # indefinitely (and block /report for OTHER sessions too) on this image, so
    # the submission response may be the only copy of this round's result.
    Path(args.report_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[submit_round] submission response saved to {args.report_out}", file=sys.stderr)

    if isinstance(result, dict) and result.get("_status") == 422:
        print("[submit_round] VALIDATION FAILED (422)", file=sys.stderr)
        return 1

    client.get_actions(args.session, args.round, args.actions_out)
    print(f"[submit_round] actions saved to {args.actions_out}", file=sys.stderr)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
