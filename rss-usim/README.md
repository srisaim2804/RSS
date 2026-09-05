# rss-usim

User simulation for the RSS marketplace: personas, query generation, the **choice
model**, and user agents. Depends only on [`rss-coms`](https://github.com/d3vdru/rss-coms).

Part of the four-repo split of [`rss`](https://github.com/d3vdru/rss) (issue #41).

## Layout

`src/ docs/ test/ config/ data/ exps/ dashboards/ steel_thread/`.

## Implementation details

### `usim.personas` — sampling

`sample_users(n, products, seed)` draws personas from five segments
(`bargain`, `premium`, `brand_loyal`, `impulsive`, `general`). The segment sets the
priors: e.g. `bargain` → high `price_sensitivity` (~8.5), `premium` → low (~2.5),
`brand_loyal` → high `brand_loyalty` (~0.85), `impulsive` → high `impulse_threshold`
(~0.8); the rest are drawn from segment-appropriate ranges. Each persona carries:

- **`ObservedFeatures`** (platform-visible): age, device, price_sensitivity,
  ad_susceptibility, review_dependency, brand_loyalty, domain_knowledge.
- **`HiddenFeatures`** (latent, never leave this repo): true_budget_ceiling,
  impulse_threshold, social_proof_weight, novelty_bias, variety_seeking.

Queries are grounded in the catalog (`_queries_from_catalog` samples product titles and
truncates a token or two to mimic real search), deduped per user. Sampling is
seed-deterministic (`seed ^ 0x5EED`).

### `usim.choice_model` — the choice function

`IndependentFunnelChoiceModel.sample(user, page: ObservationPage, knowledge, rng, decay)`
runs an independent funnel per slot: **seen → clicked → cart → purchased**. It consumes
only the platform's observable projection and **probes** `knowledge.brand_perception(brand)`
— it never imports marketplace or seller internals (this is what broke the old
`user ↔ marketplace` cycle).

Per-slot probabilities:

- `p_seen = decay ** position` (position decay).
- `p_click` builds on `0.04 + 0.5·relevance`, then multiplies by ad-susceptibility
  (sponsored slots), rating lift, `review_dependency × (trust − 0.5)`, and
  `brand_loyalty × sentiment` — so **brand perception (trust, sentiment) probed from the
  platform shifts clicks**.
- `p_cart` from affordability (`1 − price/budget_ceiling`), impulse, and trust.
- `p_purchase` from affordability, `social_proof_weight × trust`, minus a price penalty
  (`price_sensitivity × price/budget`). A purchase also requires `price ≤ budget_ceiling`.

Draws are ordered seen→click→cart→purchase per slot so the stream is reproducible;
each `UserAction` records the reached stage and the probabilities used.

### `usim.agent` — user agent

`UserAgent` is a thin session driver (`next_query`) — the placeholder for a future
LLM-backed conversational user agent (the `rss` CLAUDE.md vision: refine query, request
budget, track price drops).

## Registration

`usim.plugin` (entry point `rss.plugins → usim`) registers:

- `user_source / usim` → `list[UserPersona]` (from `cfg["products"]`, `n_users`, `seed`)
- `choice_model / independent_funnel` → `ChoiceModel`

The harness resolves these at runtime; no other party imports `usim`.

## Run

```bash
pip install -e .                              # pulls rss-coms
python -m pytest -q                           # 6 tests (incl. steel-thread smoke)
python steel_thread/run.py --path sampling    # or: choice
```
