#!/usr/bin/env python
"""Steel thread for rss-coms — runnable verification paths.

    python steel_thread/run.py --path trace      # correlated event log end-to-end
    python steel_thread/run.py --path transport   # inproc vs http parity
    python steel_thread/run.py --path system      # full four-repo simulation (needs the 3 parties)

`system` needs rss-usim, rss-mplc, rss-slrs installed; the others need only rss-coms.
"""
from __future__ import annotations

import argparse
import numpy as np

from coms.contracts import ActionEvent, new_correlation_id
from coms.trace import CorrelatedEventLog


def path_trace() -> None:
    log = CorrelatedEventLog()
    cid = new_correlation_id()
    chain = [("user", "search"), ("marketplace", "ad_source"), ("seller", "bid"),
             ("marketplace", "impress"), ("user", "click")]
    for i, (party, stage) in enumerate(chain):
        log.write(ActionEvent(correlation_id=cid, tick=i, party=party, stage=stage,
                              user_id="U1", query="wireless mouse"))
    tl = log.timeline(cid)
    assert [e.stage for e in tl] == [s for _, s in chain]
    print(f"[trace] correlation_id={cid} → {' → '.join(f'{e.party}:{e.stage}' for e in tl)}")
    print("[trace] OK")


def path_transport() -> None:
    from coms.transport import serve_marketplace, RemoteMarketplace
    from _fake import FakeMarketplace  # local helper

    local = FakeMarketplace("mkt")
    srv = serve_marketplace(local, port=8899)
    try:
        remote = RemoteMarketplace("mkt", "http://127.0.0.1:8899")
        r1 = np.random.default_rng(7)
        r2 = np.random.default_rng(7)
        from coms.contracts import UserPersona
        u = UserPersona("U1", queries=("wireless mouse",))
        a = FakeMarketplace("mkt").run_query(u, "wireless mouse", r1)
        b = remote.run_query(u, "wireless mouse", r2)
        assert abs(a.total_charged - b.total_charged) < 1e-9, (a.total_charged, b.total_charged)
        print(f"[transport] inproc == http  (charged={b.total_charged:.4f})")
        print("[transport] OK")
    finally:
        srv.shutdown()


def path_system() -> None:
    from coms.harness import SystemConfig, run_simulation
    cfg = SystemConfig()
    out = run_simulation(cfg, seed=0)
    sysm = out["system"]
    print(f"[system] marketplaces={sysm['n_marketplaces']} "
          f"revenue={sysm.get('platform_revenue', 0):.2f} "
          f"welfare={sysm.get('total_welfare', 0):.2f} "
          f"purchases={sysm.get('total_purchases', 0)}")
    tl = out["event_log"].timeline(out["last_correlation_id"])
    parties = {e.party for e in tl}
    print(f"[system] last request {out['last_correlation_id']} touched parties={sorted(parties)} "
          f"({len(tl)} events)")
    assert tl, "no correlated events"
    print("[system] OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="trace",
                    choices=["trace", "transport", "system"])
    args = ap.parse_args()
    {"trace": path_trace, "transport": path_transport, "system": path_system}[args.path]()


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    main()
