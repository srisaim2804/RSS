"""Component registry + entry-point plugin discovery.

Two plugin groups:
  * ``rss.plugins``  — first-party builtins (loaded by default when resolving components).
  * ``rss.contrib``  — community/contrib code (opt-in; loaded only via ``load_contrib()``
                       or automatically when a ``contrib:``-prefixed name is requested).

Discovery is **fail-safe**: a broken plugin is quarantined (recorded, skipped) instead of
crashing discovery for everyone — so unclean incoming code can't break core paths.
"""
from __future__ import annotations

import importlib
import sys
from importlib.metadata import entry_points
from typing import Callable

# family -> name -> factory(cfg) -> instance
_REGISTRY: dict[str, dict[str, Callable]] = {}
_LOADED_GROUPS: set[str] = set()
_PLUGIN_MODULES: set[str] = set()
_REGISTERING_MODULES: set[str] = set()           # modules that called register()
_QUARANTINE: list[tuple[str, str]] = []          # (module_or_ep, error)

CORE_GROUP = "rss.plugins"
CONTRIB_GROUP = "rss.contrib"


def register(family: str, name: str, factory: Callable) -> Callable:
    """Register a component factory. Usable as a decorator or a direct call."""
    _REGISTRY.setdefault(family, {})[name] = factory
    caller = sys._getframe(1).f_globals.get("__name__")   # module that registered
    if caller:
        _REGISTERING_MODULES.add(caller)
    return factory


def available(family: str) -> list[str]:
    return sorted(_REGISTRY.get(family, {}))


def make(family: str, cfg: dict | None = None):
    """Instantiate ``cfg['name']`` (or plugin/backend) from ``family``.

    Loads core plugins automatically; also loads contrib plugins on demand when the
    requested name is ``contrib:``-prefixed, so normal runs never touch contrib code."""
    cfg = dict(cfg or {})
    name = cfg.get("name") or cfg.get("plugin") or cfg.get("backend")
    load_plugins(CORE_GROUP)
    if isinstance(name, str) and name.startswith("contrib:"):
        load_contrib()
    fams = _REGISTRY.get(family, {})
    if name not in fams:
        raise KeyError(f"no '{name}' registered in family '{family}'; have {sorted(fams)}")
    return fams[name](cfg)


def load_plugins(group: str = CORE_GROUP) -> None:
    """Import every installed package advertising an entry point in ``group``.
    Idempotent per group; fail-safe (broken plugins are quarantined)."""
    if group in _LOADED_GROUPS:
        return
    _LOADED_GROUPS.add(group)
    try:
        eps = entry_points(group=group)
    except TypeError:  # pragma: no cover - py<3.10 shim
        eps = entry_points().get(group, [])
    for ep in eps:
        try:
            mod = ep.load()  # importing triggers register(...) calls
            _PLUGIN_MODULES.add(getattr(mod, "__name__", "") or getattr(ep, "module", ""))
        except Exception as e:  # noqa: BLE001 - quarantine, never crash discovery
            _QUARANTINE.append((f"{group}:{getattr(ep, 'name', ep)}", repr(e)))


def load_contrib() -> None:
    """Opt-in load of the ``rss.contrib`` group."""
    load_plugins(CONTRIB_GROUP)


def safe_import(modname: str) -> bool:
    """Import a module, quarantining any failure. Used by per-repo contrib loaders so a
    single broken contrib subpackage doesn't take down its siblings. Returns success."""
    try:
        importlib.import_module(modname)
        _PLUGIN_MODULES.add(modname)
        return True
    except Exception as e:  # noqa: BLE001
        _QUARANTINE.append((modname, repr(e)))
        return False


def quarantined() -> list[tuple[str, str]]:
    """Plugins that failed to load (module/ep, error). Inspect after discovery."""
    return list(_QUARANTINE)


def reset() -> None:
    """Test helper. Clears the registry AND evicts every module that registered anything
    (entry-point modules *and* the submodules they imported which call register) from the
    import cache — so a subsequent load genuinely re-registers (plain re-import is cached)."""
    _REGISTRY.clear()
    for name in _PLUGIN_MODULES | _REGISTERING_MODULES:
        sys.modules.pop(name, None)
        # also drop the parent package's attribute, else `from . import sub` rebinds the
        # stale submodule object instead of re-importing (and re-running register()).
        parent, _, child = name.rpartition(".")
        p = sys.modules.get(parent)
        if p is not None and getattr(p, child, None) is not None:
            try:
                delattr(p, child)
            except AttributeError:
                pass
    _PLUGIN_MODULES.clear()
    _REGISTERING_MODULES.clear()
    _QUARANTINE.clear()
    _LOADED_GROUPS.clear()
