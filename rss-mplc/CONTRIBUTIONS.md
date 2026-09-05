# Contributing to rss-mplc

**Canonical cross-repo guide:** https://github.com/d3vdru/rss-coms/blob/main/CONTRIBUTIONS.md
— read it first (the four-repo model, plugin rules, promotion path).

## This repo in one screen

`rss-mplc` owns the **marketplace/platform**: search, ranking, the sponsored-ad auction,
hosted campaigns, the knowledge provider, platform agents. It depends only on `rss-coms`.
Note: the private `ProductScore` latents never leave this repo — only `relevance` is
revealed on `SlotObservation`.

**What you can contribute here** (register under these families):
- `knowledge` — signals the choice model probes (`src/mplc/knowledge.py`); selectable per
  marketplace via `knowledge = "contrib:<name>"`.
- `marketplace` — a full marketplace variant (`src/mplc/marketplace.py`).
- Auction/search logic lives in `src/mplc/{auction,search,ads}.py`.

**How** — add a plugin, don't edit core:
1. Copy `src/mplc/contrib/example/` → `src/mplc/contrib/<your_feature>/`.
2. In `plugin.py`: `register("knowledge", "contrib:<name>", factory)` (or another family).
3. Add `test/contrib/test_<your_feature>.py`.
4. Enable via config (e.g. `[[marketplaces]] knowledge = "contrib:<name>"`).

**Rules:** core never imports `contrib/` (enforced by `test/test_core_no_contrib_import.py`);
contrib is opt-in and fail-safe; never push to `main` (PR in; core paths need a code-owner
review per `.github/CODEOWNERS`); thread the passed `rng`/`seed`.

**Check:** `python -m pytest -q` and `python steel_thread/run.py --path full`.
