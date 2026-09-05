# contrib/ — contribution staging area

Drop new, in-progress, or not-yet-hardened code here. It plugs into the same interfaces
as the builtins but stays **isolated and opt-in** until promoted.

## Rules

1. **One-way dependency.** `contrib/` may import core (`coms.contracts`, `coms.interfaces`,
   `coms.infra`), but **core must never import `contrib/`**. A test enforces this.
2. **Register, don't edit.** Add capability by registering a new implementation — do not
   modify builtin files.
3. **Namespaced names.** Register under a `contrib:` prefix, e.g.
   `register("choice_model", "contrib:my_model", factory)`.
4. **Opt-in only.** Contrib loads via `coms.infra.load_contrib()`, or automatically when a
   `contrib:`-prefixed name is requested. Normal runs never touch it.
5. **Fail-safe.** A contrib subpackage that raises on import is quarantined
   (`coms.infra.quarantined()`), not fatal.

## Add a contribution

```
src/<pkg>/contrib/<your_feature>/
    __init__.py
    plugin.py        # registers your component
    ...              # the rest of your code
test/contrib/
    test_<your_feature>.py
```

`plugin.py`:

```python
from coms.infra import register

def _make(cfg):
    return MyThing(...)

register("choice_model", "contrib:my_model", _make)
```

Enable it in config: `choice_model = "contrib:my_model"` (or call `load_contrib()`).

## Promotion to core

A contribution graduates to a builtin when it (a) has core-quality tests, (b) needs no
new/changed interface (interface changes get their own review), and (c) a code owner signs
off. Until then it lives here, usable by whoever opts in, invisible to everyone else.
See the repo `CONTRIBUTIONS.md`.
