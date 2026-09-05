import tempfile, os
from coms.contracts import ActionEvent, new_correlation_id
from coms.trace import CorrelatedEventLog


def _write_request(log, cid):
    chain = [("user", "search"), ("marketplace", "ad_source"), ("seller", "bid"),
             ("marketplace", "impress"), ("user", "click")]
    for i, (party, stage) in enumerate(chain):
        log.write(ActionEvent(correlation_id=cid, tick=i, party=party, stage=stage,
                              user_id="U1", query="mouse"))
    return chain


def test_timeline_reconstructs_in_order_memory():
    log = CorrelatedEventLog()
    cid = new_correlation_id()
    other = new_correlation_id()
    _write_request(log, cid)
    log.write(ActionEvent(correlation_id=other, tick=0, party="user", stage="search"))
    tl = log.timeline(cid)
    assert [e.party for e in tl] == ["user", "marketplace", "seller", "marketplace", "user"]
    assert all(e.correlation_id == cid for e in tl)   # no bleed from `other`


def test_timeline_sqlite_roundtrip():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "events.sqlite")
    log = CorrelatedEventLog(path)
    cid = new_correlation_id()
    chain = _write_request(log, cid)
    log.write_many([])  # flush/commit
    tl = log.timeline(cid)
    assert [e.stage for e in tl] == [s for _, s in chain]
    log.close()
    # reopen → persisted
    log2 = CorrelatedEventLog(path)
    assert len(log2.timeline(cid)) == len(chain)
    log2.close()
