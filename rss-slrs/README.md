# rss-slrs

Seller simulation for the RSS marketplace: seller sampling from distributions,
campaign management, **bidding/pacing**, seller agents, and the RTB bidder. Depends
only on [`rss-coms`](https://github.com/d3vdru/rss-coms).

Part of the four-repo split of [`rss`](https://github.com/d3vdru/rss) (issue #41).

## Layout

`src/ docs/ test/ config/ data/ exps/ dashboards/ steel_thread/`.

## Implementation details

### `slrs.sellers` — sampling

`sample_sellers(products, n_sellers, seed)` groups the catalog by brand, then folds the
brands into `n_sellers` buckets (each seller owns whole brands). Each seller gets a
`cogs_ratio ∈ 0.35–0.65` and `value_per_conversion_ratio ∈ 0.2–0.4`, seed-deterministic
(`seed ^ 0x5E11E5`). Sellers with no products are dropped.

### `slrs.campaigns` — campaign construction

`build_campaigns(sellers, product_map, seed)` creates one `CampaignSpec` per seller over
its products. Keyword bids are derived from product titles: every distinct title token
becomes a keyword, priced off product value (`0.3 + price·0.004`, taking the max across
the seller's products). Initial `BidControls` set `bid_multiplier=1.0`, a
per-product-scaled `daily_budget` (~`U(20,80)·n_products`), and `pace_mode="even"`.

### `slrs.policy` — the fleet (bidding logic)

`SellerFleet` satisfies coms `SellerPolicy` and owns all of this plugin's
sellers/campaigns:

- `initial_campaigns()` → `(specs, controls)` for the marketplace to host.
- `step(round_idx, snapshot)` → updated `BidControls`. The default `adaptive_roas`
  strategy reads `seller_roas_mean` from the platform snapshot and nudges every
  `bid_multiplier` — `×1.05` when ROAS > 2, `×0.95` when ROAS < 1, unchanged otherwise —
  clamped to `[0.5, 2.0]`. `BidControls` are frozen, so updates use `dataclasses.replace`.
  `strategy="deterministic"` holds bids fixed.
- `observe(snapshot)` stores the latest snapshot (hook for richer learners).
- `bidder()` → an `RTBBidder` for the RTB topology.

Bidding lives **here** (seller side); the campaign object lives on the platform (hosted
model). This mirrors real sponsored-ads: the seller controls bids, the platform hosts the
ad and sources it.

### `slrs.bidder` — RTB

`RTBBidder.bid(request)` is used only when a marketplace runs `ad_sourcing="rtb"`. It
matches the `BidRequest.query` tokens against campaign keywords and returns ranked
`BidResponse`s (creative + `bid = max matching keyword bid × bid_multiplier`), capped at
`request.n_slots`. Only observable user features (segment, device) reach the seller —
never the hidden persona traits.

### `slrs.agent` — seller agent

`SellerAgent` is a thin wrapper — the home for a future LLM-backed seller agent doing
cross-platform inventory/budget planning.

## Registration

`slrs.plugin` (entry point `rss.plugins → slrs`) registers `seller_source/slrs` →
`SellerFleet`. Disabling this plugin (or `[sellers] enabled=false`) yields a two-party
search-only system.

## Run

```bash
pip install -e .                       # pulls rss-coms
python -m pytest -q                    # 7 tests (incl. steel-thread smoke)
python steel_thread/run.py --path campaign   # sample | campaign | bid
```
