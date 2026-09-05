from coms.infra import registry


def test_register_and_make():
    registry.register("widget", "basic_x", lambda cfg: {"kind": "basic", **cfg})
    assert "basic_x" in registry.available("widget")
    obj = registry.make("widget", {"name": "basic_x", "size": 3})
    assert obj["kind"] == "basic" and obj["size"] == 3


def test_make_unknown_raises():
    try:
        registry.make("widget", {"name": "definitely_absent_zzz"})
        assert False
    except KeyError as e:
        assert "definitely_absent_zzz" in str(e)


def test_load_plugins_idempotent():
    # additive + cached: calling twice must not raise or double-register
    registry.load_plugins()
    before = set(registry.available("widget"))
    registry.load_plugins()
    assert set(registry.available("widget")) == before
