# Architecture (four-repo split)

```
rss-usim ─┐
rss-mplc ─┼─► rss-coms   (leaf: contracts, interfaces, infra, health, trace, transport, harness)
rss-slrs ─┘
```

Party repos depend only on `rss-coms`. They never import each other; the harness
resolves concrete implementations at runtime from the registry, populated by
`rss.plugins` entry points. So the package DAG is acyclic even though the harness
drives all three parties.

## Seams (interfaces in `coms.interfaces`)

- **`MarketplaceService`** — `run_query`, `run_queries_batch`, `reset_day`,
  `upsert_campaign`, `set_controls`, `snapshot`. The network boundary
  (`coms.transport` provides an HTTP implementation).
- **`ChoiceModel`** — consumes the platform's `ObservationPage` and probes a
  `KnowledgeProvider`; never sees `ProductScore` or `Campaign` internals.
- **`KnowledgeProvider`** — served by rss-mplc; v1 exposes `brand_perception`.
- **`SellerPolicy`** (fleet) — `initial_campaigns`, `step`, `observe`, `bidder`.
- **`CampaignRegistry`** (hosted) / **`BidderService`** (RTB) — the two ad-sourcing
  topologies, selected by `ad_sourcing` per marketplace.

## Observable-features model

The marketplace owns the latent `ProductScore` (ctr/cvr/relevance). It reveals only
a projection (`SlotObservation`: title, price, rating, brand, relevance, sponsored
badge). The choice model reads that projection and probes `brand_perception` for
extra signal. This is what breaks the old `user ↔ marketplace` import cycle.

## Correlated event log

The harness mints a `correlation_id` per search; it rides on every
`MarketplaceService`/`BidderService` call and is stamped on every `ActionEvent`.
`coms.trace.CorrelatedEventLog.timeline(id)` returns the ordered chain
(user search → ad source → bid → impress → click → settle) — across nodes too,
since the transport propagates the id.

## Modes

- **Two-party:** `[sellers] enabled=false` → no seller fleet, `ad_slots=0`,
  organic-only.
- **Multi-marketplace:** multiple `[[marketplaces]]`; per-market snapshots plus a
  system-wide aggregate.
- **RTB:** `ad_sourcing="rtb"` → marketplace calls the seller `BidderService` per
  request instead of sourcing from its hosted `CampaignRegistry`.
