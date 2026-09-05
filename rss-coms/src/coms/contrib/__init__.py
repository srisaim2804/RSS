"""Staging area for community / in-progress contributions.

Code here registers against the same `coms.interfaces` as the builtins but is **opt-in**:
it loads only via `coms.infra.load_contrib()` or when a `contrib:`-prefixed name is
requested. **Core never imports this package** (enforced by a test) — the dependency is
one-way (`contrib → core`), so incoming code can add capabilities without touching or
breaking the core.

Add a contribution as a subpackage with a `plugin.py`:

    src/<pkg>/contrib/<your_feature>/
        __init__.py
        plugin.py       # calls coms.infra.register("<family>", "contrib:<name>", factory)

The loader auto-discovers it; no pyproject edit needed. See `contrib/README.md`.
"""
