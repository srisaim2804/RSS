# Contributing to rss-slrs

**Canonical cross-repo guide:** https://github.com/d3vdru/rss-coms/blob/main/CONTRIBUTIONS.md
— read it first (the four-repo model, plugin rules, promotion path).

## This repo in one screen

`rss-slrs` owns **seller behaviour**: seller sampling, campaign management, bidding/pacing,
seller agents, the RTB bidder. It depends only on `rss-coms`. Bidding lives here; the
campaign object lives on the platform (hosted model).

**What you can contribute here** (register under these families):
- `seller_source` — a seller fleet + its bidding policy (`src/slrs/policy.py`); selectable
  via `[sellers] plugin = "contrib:<name>"`.
- RTB bidding (`src/slrs/bidder.py`).

**How** — add a plugin, don't edit core:
1. Copy `src/slrs/contrib/example/` → `src/slrs/contrib/<your_feature>/`.
2. In `plugin.py`: `register("seller_source", "contrib:<name>", factory)`.
3. Add `test/contrib/test_<your_feature>.py`.
4. Enable via config (`[sellers] plugin = "contrib:<name>"`).

**Rules:** core never imports `contrib/` (enforced by `test/test_core_no_contrib_import.py`);
contrib is opt-in and fail-safe; never push to `main` (PR in; core paths need a code-owner
review per `.github/CODEOWNERS`); thread the passed `rng`/`seed`.

**Check:** `python -m pytest -q` and `python steel_thread/run.py --path campaign`.
