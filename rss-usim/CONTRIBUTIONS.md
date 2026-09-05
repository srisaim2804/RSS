# Contributing to rss-usim

**Canonical cross-repo guide:** https://github.com/d3vdru/rss-coms/blob/main/CONTRIBUTIONS.md
— read it first (the four-repo model, plugin rules, promotion path).

## This repo in one screen

`rss-usim` owns **user behaviour**: personas, query generation, the choice model, user
agents. It depends only on `rss-coms`.

**What you can contribute here** (register under these families):
- `choice_model` — how users click/cart/buy (`src/usim/choice_model.py`)
- `user_source` — persona/cohort generation (`src/usim/personas.py`)

**How** — add a plugin, don't edit core:
1. Copy `src/usim/contrib/example/` → `src/usim/contrib/<your_feature>/`.
2. In `plugin.py`: `register("choice_model", "contrib:<name>", factory)`.
3. Add `test/contrib/test_<your_feature>.py`.
4. Enable via config (`choice_model = "contrib:<name>"`) or `coms.infra.load_contrib()`.

**Rules:** core never imports `contrib/` (enforced by `test/test_core_no_contrib_import.py`);
contrib is opt-in and fail-safe; never push to `main` (PR in; core paths need a code-owner
review per `.github/CODEOWNERS`); thread the passed `rng`/`seed`.

**Check:** `python -m pytest -q` and `python steel_thread/run.py --path choice`.
