# rss-mplc

Marketplace/platform for the RSS simulation: organic search + ranking, the
**sponsored-ad auction**, hosted campaigns, the knowledge provider, correlated event
emission, and platform agents. Depends only on
[`rss-coms`](https://github.com/d3vdru/rss-coms).

Part of the four-repo split of [`rss`](https://github.com/d3vdru/rss) (issue #41).

## Layout

`src/ docs/ test/ config/ data/ exps/ dashboards/ steel_thread/`.

## Implementation details

### `mplc.scoring` — private latents

`ProductScore` (ctr, cvr, relevance) is **private to this repo** — it never crosses a
contract boundary. `score_product(query, product, rng)` computes:

- `relevance = clip(0.20 + 0.60·overlap + N(0,0.05))`, where `overlap` is the
  query/title token-set overlap;
- `ctr = clip(0.03 + 0.02·rating/5 + N(0,0.01))`;
- `cvr = clip(0.12 − 0.08·min(price/400,1) + N(0,0.015))`.

`quality = max(1e-3, relevance)` is the auction weight. Only `relevance` is later
revealed on `SlotObservation`.

### `mplc.search` — organic retrieval

`MockSearchIndex` ranks catalog products by query/title word overlap (deterministic tie-break
on `product_id`). This is the interface seam where the monorepo's bm25s/tantivy/lancedb
backends can drop in unchanged.

### `mplc.ads` — hosted campaign registry (default)

`HostedCampaignRegistry` is the **hosted** ad model: the created campaign lives on the
platform. `upsert_campaign(spec)` stores the definition and builds an **inverted keyword
index** (`token → {campaign_id}`) for O(candidates) matching; `set_controls(controls)`
records the seller's per-round bid/budget/pacing. `candidates(query)` returns active,
in-budget campaigns whose keywords overlap the query, each resolved to its best-matching
product with an effective bid (`max keyword bid × bid_multiplier`). `charge` accrues
daily spend; `reset_day` clears it.

### `mplc.auction` — allocation + pricing

`run_auction(query, candidates, n_slots, rng, mechanism, min_quality)` scores each
candidate (private `score_product`), screens on `min_quality`, ranks by
`bid × quality`, and prices the winners:

- **GSP** (default): `cpc_i = (bid_{i+1}·q_{i+1}) / q_i`, capped at the winner's own bid;
  the last slot pays a `0.5×bid` floor.
- **first_price**: `cpc_i = bid_i`.

### `mplc.knowledge` — brand perception (v1)

`BrandPerceptionProvider.brand_perception(brand)` returns `{trust ∈ 0.3–0.9,
sentiment ∈ −1..1}`, derived deterministically from a SHA-256 of the brand string
(reproducible, cached per brand). This is the v1 `KnowledgeProvider` signal (issue #41
decision); a reviews-backed KG/SQLite store can replace `_derive` later without touching
the interface.

### `mplc.marketplace` — the seam

`Marketplace.run_query(user, query, rng, correlation_id)`:

1. emit `user:search`;
2. if `ad_slots>0`: source candidates (hosted registry, or a seller `BidderService` when
   `ad_sourcing="rtb"`), run the auction, emit `seller:ad_source` per winner;
3. build the SERP — ad winners first, then deduped organic hits — and project it to an
   `ObservationPage` (revealing relevance only);
4. call the injected `ChoiceModel.sample(user, page, self, rng, decay)` (the marketplace
   *is* the `KnowledgeProvider` passed in);
5. settle each action: clicked ad → charge cpc (platform revenue, seller ad_spend);
   purchased → seller revenue/cogs, user surplus `= max(0, price·(0.6+0.08·rating) −
   price)`, social value `= surplus + (revenue − cogs)`; record to `UtilityLedger` +
   `MetricsTracker`; emit `user:<action>`;
6. emit `marketplace:settle`, flush all events to the correlated log, return `QueryResult`.

`snapshot()` returns `extract_metrics(ledger, tracker)` plus `ad_load`. `reset_day`
delegates to the registry (daily budgets); the ledger accumulates across the whole run.

### `mplc.agent` — platform agent

`PlatformAgent.step` adjusts the `Regulator.min_quality` screen per round (optional
platform-side policy).

## Modes

- **hosted** (default) — campaigns live here; sellers push controls.
- **rtb** — inject a `BidderService`; the marketplace calls `bid(request)` per query
  (only observable user features are shared).
- **two-party** — `ad_slots=0` → organic only, auction skipped, no ad revenue.

## Registration

`mplc.plugin` (entry point `rss.plugins → mplc`) registers `marketplace/mplc` and
`knowledge/brand_perception`.

## Run

```bash
pip install -e .                       # pulls rss-coms
python -m pytest -q                    # 11 tests (incl. steel-thread smoke)
python steel_thread/run.py --path full   # search | auction | knowledge | full
```
