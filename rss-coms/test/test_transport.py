import numpy as np

from coms.contracts import UserPersona, CampaignSpec, KeywordBid, QueryResult
from coms.transport import encode, decode, serve_marketplace, RemoteMarketplace


def test_codec_roundtrip_persona():
    u = UserPersona("U1", segment="premium", queries=("a", "b"))
    assert decode(encode(u)) == u


def test_codec_roundtrip_campaign():
    c = CampaignSpec("c1", "s1", ("P1", "P2"), (KeywordBid("mouse", 1.0),))
    assert decode(encode(c)) == c


class _Fake:
    id = "mkt"

    def run_query(self, user, query, rng, *, correlation_id=None):
        cpc = float(rng.uniform(0.1, 1.0))
        clicked = bool(rng.random() < 0.5)
        return QueryResult(query, user.user_id, correlation_id or "R0",
                           total_charged=cpc if clicked else 0.0)

    def run_queries_batch(self, items, rng):
        return [self.run_query(u, q, rng, correlation_id=c) for u, q, c in items]

    def reset_day(self): ...
    def upsert_campaign(self, s): ...
    def set_controls(self, c): ...
    def snapshot(self): return {}


def test_inproc_http_parity():
    srv = serve_marketplace(_Fake(), port=8912)
    try:
        remote = RemoteMarketplace("mkt", "http://127.0.0.1:8912")
        u = UserPersona("U1", queries=("mouse",))
        # same seed on both paths → identical rng stream → identical charge
        local_res = [_Fake().run_query(u, "mouse", np.random.default_rng(3))]
        r = np.random.default_rng(3)
        remote_res = [remote.run_query(u, "mouse", r)]
        assert abs(local_res[0].total_charged - remote_res[0].total_charged) < 1e-9
    finally:
        srv.shutdown()
