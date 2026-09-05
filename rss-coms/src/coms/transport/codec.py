"""(De)serialize the wire contracts. JSON over the stdlib — no extra deps.

Uses a ``__type__`` tag so nested frozen dataclasses round-trip exactly.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass

from coms import contracts as C

# types that may cross the wire
_TYPES = {
    "ObservedFeatures": C.ObservedFeatures, "HiddenFeatures": C.HiddenFeatures,
    "UserPersona": C.UserPersona, "Product": C.Product, "KeywordBid": C.KeywordBid,
    "CampaignSpec": C.CampaignSpec, "BidControls": C.BidControls,
    "SlotObservation": C.SlotObservation, "ObservationPage": C.ObservationPage,
    "UserAction": C.UserAction, "SettleResult": C.SettleResult,
    "QueryResult": C.QueryResult, "ActionEvent": C.ActionEvent,
    "BidRequest": C.BidRequest, "BidResponse": C.BidResponse,
}
_TUPLE_FIELDS = {"queries", "product_ids", "keyword_bids", "target_segments",
                 "negative_keywords", "slots", "actions", "settle", "badges"}


def encode(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        out = {"__type__": type(obj).__name__}
        for f in fields(obj):
            out[f.name] = encode(getattr(obj, f.name))
        return out
    if isinstance(obj, (list, tuple)):
        return [encode(x) for x in obj]
    return obj


def decode(data):
    if isinstance(data, dict) and "__type__" in data:
        cls = _TYPES[data["__type__"]]
        kwargs = {}
        for f in fields(cls):
            v = decode(data[f.name])
            if f.name in _TUPLE_FIELDS and isinstance(v, list):
                v = tuple(v)
            kwargs[f.name] = v
        return cls(**kwargs)
    if isinstance(data, list):
        return [decode(x) for x in data]
    return data
