# rss-coms

Commons for the RSS marketplace simulation. The **leaf** package every other repo
depends on; it never imports a party package (parties self-register via entry points).

Part of the four-repo split of [`rss`](https://github.com/d3vdru/rss) (issue #41):
`rss-coms` · [`rss-mplc`](https://github.com/d3vdru/rss-mplc) ·
[`rss-usim`](https://github.com/d3vdru/rss-usim) ·
[`rss-slrs`](https://github.com/d3vdru/rss-slrs).

## Layout

`src/ docs/ test/ config/ data/ exps/ dashboards/ steel_thread/` (standard across all four repos).

> **Adding functionality?** [`docs/quickstart.md`](docs/quickstart.md) is the go-to
> cookbook — the exact code touchpoints across repos to enable new information sharing,
> swap the choice model, write a bidding algorithm, add a metric, run across nodes, etc.

## Internal layers (strict downward dependency)

```
contracts  ←  interfaces  ←  infra / health / trace / transport  ←  harness
```

Party repos import only the lower layers (`contracts`, `interfaces`, `infra`,
`health`, `trace`). The `harness` sits on top and resolves parties at runtime, so no
party is ever imported statically — the package DAG stays acyclic.

## Implementation details

### `coms.contracts` — the wire schema (frozen dataclasses)

Three tiers, deliberately separated so no party shares another's internals:

- **definitions** (party-owned inputs): `UserPersona` (`ObservedFeatures` +
  `HiddenFeatures`), `Product`, `CampaignSpec`, `BidControls`, `KeywordBid`.
- **projections** (what one party reveals): `SlotObservation` / `ObservationPage` —
  the observable projection of the marketplace's internal page. Carries
  title/price/rating/brand/**revealed relevance**/`is_sponsored` + settlement
  bookkeeping (`campaign_id`, `cpc`); it does **not** carry ctr/cvr. `ProductScore`
  lives in rss-mplc, never here.
- **outcomes** (event journal): `UserAction`, `SettleResult`, `QueryResult`,
  `ActionEvent`, plus `Trace` and `BidRequest`/`BidResponse` (RTB).

`new_correlation_id()` mints monotonic ids (`R00000001`, …) from a process counter —
no wall clock, so runs stay reproducible.

### `coms.interfaces` — Protocols (structural, `@runtime_checkable`)

`MarketplaceService` (`run_query`, `run_queries_batch`, `reset_day`,
`upsert_campaign`, `set_controls`, `snapshot`), `ChoiceModel`
(`sample(user, page, knowledge, rng, decay)`), `KnowledgeProvider`
(`brand_perception` in v1), `SellerPolicy` (the fleet: `initial_campaigns`, `step`,
`observe`, `bidder`), `CampaignRegistry` (hosted) / `BidderService` (RTB),
`MetricsSink`, `SearchIndex`, `EventStore`, plus base `Agent`/`Strategy`/`WorldView`.

### `coms.infra.registry` — entry-point plugin discovery

`register(family, name, factory)` populates a `family → name → factory` map (used as a
decorator or a direct call). `load_plugins()` reads the `rss.plugins` entry-point group
via `importlib.metadata` and imports each advertised module, whose import triggers its
`register(...)` calls. `make(family, cfg)` resolves `cfg["name"]` (or `plugin`) and
instantiates. `reset()` (test helper) also evicts plugin modules from `sys.modules` so a
later `load_plugins()` genuinely re-registers (plain re-import is cached and would not).

### `coms.trace` — correlated event log

`CorrelatedEventLog(path=None)` is an in-memory list (fast; tests / steel thread) or a
SQLite file (persistent; dashboards) — same `EventStore` interface (`write`,
`write_many`, `close`). Every `ActionEvent` carries `correlation_id` (indexed) +
`tick` + `party` + `stage` (+ optional `parent_id`). `timeline(correlation_id)` returns
the tick-ordered chain for one request:

```
user:search → seller:ad_source → user:seen → user:clicked → user:purchased → marketplace:settle
```

so `SELECT … WHERE correlation_id='R00000001' ORDER BY tick` reconstructs the whole
path across all three parties.

### `coms.transport` — HTTP `MarketplaceService`

`codec.encode/decode` round-trip the contract dataclasses through JSON with a
`__type__` tag (nested frozen dataclasses reconstruct exactly; tuple fields restored).
`serve_marketplace(local, host, port)` starts a threaded stdlib HTTP server;
`RemoteMarketplace(id, url)` is the client stub. **rng parity:** the client ships
`rng.bit_generator.state` with each request and adopts the advanced state from the
response, so an `http` run reproduces an `inproc` run bit-for-bit (asserted in
`test/test_transport.py`).

### `coms.health` — the measurement plane

- `UtilityLedger` accumulates per-party surplus: `PlatformHealth` (ad_revenue,
  value_created, impressions), `SellerUtility` (profit = gross − cogs − ad_spend, roas,
  acos), `UserUtility` (surplus, purchases).
- `MetricsTracker` (a `MetricsSink`) keeps per-campaign impression/click/conversion
  counters → ctr/cvr/acos/roas.
- `extract_metrics(ledger, tracker)` flattens to the standard dict
  (`platform_revenue`, `seller_profit_total`, `user_surplus_per_session`,
  `total_welfare = platform + seller_profit + user_surplus`, `mean_ctr`, …).
- `bootstrap_ci` / `compare_arms` for A/B stats; `RoundUtilityStore` persists per-round
  snapshots for dashboards.

### `coms.harness` — the orchestrator

`load_system(system.toml)` → `SystemConfig`. `run_simulation(cfg, seed, event_log)`:
mints a neutral `synth_catalog` (so two-party mode still has products), resolves
`user_source` + `choice_model` (usim), and for each `[[marketplaces]]` entry resolves a
`seller_source` fleet (slrs, unless two-party) and the `marketplace` (mplc). Hosted
campaigns are `upsert`ed once; then each round: `reset_day` → fleet `step` emits fresh
`BidControls` → `queries_per_round` searches (each with a new `correlation_id`) → fleet
`observe`. Returns per-market snapshots + a summed system aggregate + the event log +
the last correlation id.

## Run

```bash
pip install -e .
python -m pytest -q                           # 23 tests (incl. steel-thread smoke)
python steel_thread/run.py --path trace       # correlated log
python steel_thread/run.py --path transport    # inproc vs http parity
python steel_thread/run.py --path system       # full sim — needs the 3 party repos
```

## Configuration

`config/system.example.toml` declares the topology (parties, transports, marketplaces).
`sellers.enabled=false` → two-party mode; multiple `[[marketplaces]]` → multi-marketplace.
Defaults: `ad_sourcing = hosted`, `knowledge = brand_perception`.
