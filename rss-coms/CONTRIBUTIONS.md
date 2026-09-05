# Contributing to the RSS simulation (rss-coms · rss-usim · rss-mplc · rss-slrs)

Welcome. This is the **canonical onboarding guide for all four repos**. `rss-coms` is the
hub; the party repos link here.

## 1. The mental model (read this first)

The system is split into four repos:

| Repo | Owns | You contribute here when… |
|---|---|---|
| [`rss-coms`](https://github.com/d3vdru/rss-coms) | contracts, interfaces, registry, health, correlated log, transport, harness | you change a **shared data shape or capability**, a metric, or the run loop |
| [`rss-usim`](https://github.com/d3vdru/rss-usim) | personas, query gen, **choice model**, user agents | you change **user behaviour** |
| [`rss-mplc`](https://github.com/d3vdru/rss-mplc) | search, ranking, **auction**, hosted campaigns, knowledge, platform agents | you change the **marketplace/platform** |
| [`rss-slrs`](https://github.com/d3vdru/rss-slrs) | seller sampling, campaigns, **bidding/pacing**, RTB | you change **seller behaviour** |

**Golden rule:** anything crossing a repo boundary goes through a `coms.contracts`
(dataclass) or `coms.interfaces` (Protocol). **Party repos never import each other.** Your
code plugs in by **registering** an implementation against an interface — you almost never
edit an existing file. See [`docs/quickstart.md`](docs/quickstart.md) for the exact
touchpoints of each kind of change.

## 2. Where your code goes: `contrib/` first

Every repo has `src/<pkg>/contrib/` — a **staging area** for new, in-progress, or
not-yet-hardened code. It is **isolated and opt-in**:

- `contrib/` may import core; **core never imports `contrib/`** (a test enforces this).
- Contrib loads only via `coms.infra.load_contrib()` or when a `contrib:`-prefixed name is
  requested — so a normal run and the core test suite never touch it.
- Discovery is **fail-safe**: a contrib package that breaks on import is *quarantined*
  (`coms.infra.quarantined()`), never fatal to others.

This means **your unfinished or experimental code cannot break the core or other people's
work.** It sits in `contrib/` until it's deliberately promoted.

## 3. Add a contribution (the 5-minute path)

1. Copy the `example/` folder in that repo's `src/<pkg>/contrib/`:
   ```
   src/<pkg>/contrib/<your_feature>/
       __init__.py
       plugin.py
   ```
2. In `plugin.py`, register against the right family under a `contrib:` name:
   ```python
   from coms.infra import register
   register("choice_model", "contrib:my_model", lambda cfg: MyModel(**cfg))
   ```
   Family per repo: `choice_model`/`user_source` (usim), `marketplace`/`knowledge` (mplc),
   `seller_source` (slrs), or any new family you introduce. The loader auto-discovers your
   folder — **no `pyproject.toml` edit needed.**
3. Add a test under `test/contrib/test_<your_feature>.py`.
4. Enable it in a config (`choice_model = "contrib:my_model"`) or `load_contrib()` in code.
5. Run the checks (section 5).

If your change needs a **new shared field or capability**, that's a `coms` change (a
contract field or an interface method) — open a separate, focused PR on `rss-coms` for it
first; keep interface changes small and reviewed on their own.

## 4. Branch & PR conventions

- **Never push to `main`.** Branch from `main`; PR into `main`.
- Prefer landing new work in `contrib/` (or a `contrib/*` feature branch). Promotion to
  core is a separate, deliberate PR.
- One logical change per PR. Reference the issue.
- `main` is protected; core paths require a code-owner review (see `.github/CODEOWNERS`),
  `contrib/**` is lighter.
- Commit trailer: end messages with a `Co-Authored-By:` line if pairing/AI-assisted.

## 5. Before you open a PR

```bash
pip install -e .            # (and the other repos if your change spans them)
python -m pytest -q         # core suite must stay green
python steel_thread/run.py --path <a-path>     # exercise your area
# four-repo smoke (from rss-coms, all four installed):
python steel_thread/run.py --path system
```

Your contrib gets its own test job; **it must not break the core suite** (it can't, if you
followed section 2). Thread the passed `rng`/`seed` — no wall-clock, no unseeded random
(determinism is asserted by `rss-coms/test/test_system.py`).

## 6. Promotion: contrib → core

A contribution graduates to a builtin when:

1. it has **core-quality tests** (happy + boundary + failure),
2. it needs **no new/changed interface** (or that change already landed + was reviewed),
3. it's been **exercised** (config/steel-thread) and is stable, and
4. a **code owner signs off**.

Promotion = move it out of `contrib/`, drop the `contrib:` prefix, register it under
`rss.plugins`, and delete the staging copy. Until then it lives in `contrib/`, usable by
whoever opts in, invisible to everyone else.

## 7. Reference

- [`docs/quickstart.md`](docs/quickstart.md) — cross-repo touchpoints per change type.
- [`docs/architecture.md`](docs/architecture.md) — topology, interfaces, correlated log.
- `src/<pkg>/contrib/README.md` — the per-repo contrib rules.
