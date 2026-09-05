"""Contrib is opt-in, fail-safe, and isolated from core. Order-independent (no reset)."""
from importlib.metadata import entry_points

from coms.infra import registry


def test_contrib_is_a_separate_optin_group():
    # the design guarantee: contrib lives in `rss.contrib`, NOT the core `rss.plugins`,
    # so core runs never auto-load it.
    core = {ep.name for ep in entry_points(group="rss.plugins")}
    contrib = {ep.name for ep in entry_points(group="rss.contrib")}
    assert "coms" in contrib
    assert "coms" not in core


def test_contrib_loads_on_demand():
    registry.load_contrib()
    obj = registry.make("demo", {"name": "contrib:hello", "x": 1})
    assert obj["msg"] == "hello from coms contrib" and obj["cfg"]["x"] == 1


def test_contrib_prefixed_name_autoloads():
    # a contrib: name pulls contrib in even without an explicit load_contrib()
    assert registry.make("demo", {"name": "contrib:hello"})["msg"].startswith("hello")


def test_broken_plugin_is_quarantined_not_fatal():
    ok = registry.safe_import("coms.contrib._does_not_exist.plugin")
    assert ok is False
    assert any("does_not_exist" in mod for mod, _ in registry.quarantined())
    # good plugins still resolve afterwards
    assert registry.make("demo", {"name": "contrib:hello"})["msg"].startswith("hello")


def test_reset_allows_clean_reload():
    # reset() must fully re-register on the next load (parent-attr eviction, not just sys.modules)
    registry.reset()
    registry.load_plugins()          # core group
    assert "independent_funnel" in registry.available("choice_model")
