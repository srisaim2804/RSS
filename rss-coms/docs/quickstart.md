# Quick-Start: adding functionality across the four repos

The go-to doc for setting up an experiment — enabling new information sharing,
swapping the choice model, writing a bidding algorithm, adding a metric, and so on.
It lists the exact **code touchpoints per repo** for each change.

## The one rule

Anything that crosses a service boundary goes through **`rss-coms`** — a **contract**
(a dataclass in `coms.contracts`) or an **interface** (a Protocol in `coms.interfaces`).
Party repos (`rss-usim`, `rss-mplc`, `rss-slrs`) depend only on `rss-coms` and **never
import each other**. Concrete code self-registers via an `rss.plugins` entry point and is
resolved at runtime by the harness. So every change is one of four touchpoint kinds:

| Kind | Where | When you need it |
|---|---|---|
| **C** — contract | `rss-coms/src/coms/contracts/` | new data must travel between services |
| **I** — interface | `rss-coms/src/coms/interfaces/` | a new *capability* one service asks of another |
| **P** — party impl + register | a party repo's `src/<pkg>/…` + `plugin.py` | the actual logic |
| **W** — wiring | `system.toml` / `coms.harness` | turn it on, pick the variant |

A change that "touches two services" is almost always: **C or I in coms** (the shared
seam) **+ P in each of the two party repos** **+ maybe W** to enable it.

Reproducibility: never use wall-clock or unseeded randomness — thread the passed
`rng`/`seed`. Determinism is asserted by `rss-coms/test/test_system.py`.

After any change, run the affected repo's `steel_thread` and `pytest`, then the
four-repo check: `python rss-coms/steel_thread/run.py --path system`.

---

## Recipe 1 — Modify or add a choice model  *(1 service: rss-usim)*

Change how users behave. No contract change if you only use what's already on the page.

1. **P · rss-usim** — edit `src/usim/choice_model.py` (tune `IndependentFunnelChoiceModel`
   `p_seen/p_click/p_cart/p_purchase`) **or** add a new class:
   ```python
   class SessionBudgetChoiceModel:
       def sample(self, user, page, knowledge, rng, position_decay=0.7):
           ...  # return list[UserAction], one per page.slots
   register("choice_model", "session_budget", lambda cfg: SessionBudgetChoiceModel())
   ```
2. **W · config** — select it: `[users] choice_model = "session_budget"`.
3. **Verify** — `usim/steel_thread/run.py --path choice`; add a case to `usim/test/test_usim.py`.

> The model reads only `page` (`ObservationPage`) and probes `knowledge`. If it needs a
> signal that isn't on either, use Recipe 2 or 3.

---

## Recipe 2 — Share a new piece of information platform → user  *(2 services: rss-mplc + rss-usim, via a coms contract)*

Example: reveal a "delivery_days" badge so the choice model can react to it.

1. **C · rss-coms** — add the field to the projection in
   `src/coms/contracts/projections.py`:
   ```python
   @dataclass(frozen=True)
   class SlotObservation:
       ...
       delivery_days: int = 3        # NEW — platform-revealed
   ```
   (If it must also survive the network, that's automatic — the transport codec walks
   dataclass fields; just make sure it's a JSON-friendly type.)
2. **P · rss-mplc** — populate it where slots are built in
   `src/mplc/marketplace.py::run_query` (both the ad-slot and organic-slot
   `SlotObservation(...)` constructions).
3. **P · rss-usim** — consume it in `src/usim/choice_model.py` (e.g. fold
   `slot.delivery_days` into `p_purchase`).
4. **Verify** — `mplc/steel_thread --path full`, `usim/steel_thread --path choice`, then
   `rss-coms/steel_thread --path system`.

> Keep the split honest: only reveal what the platform *chooses* to. Latent scoring
> (`ProductScore`) stays private in `rss-mplc` and must not leak onto `SlotObservation`.

---

## Recipe 3 — Add a new knowledge signal the user can probe  *(2 services: rss-mplc + rss-usim, via a coms interface)*

`brand_perception` is the v1 signal. To add, say, `review_summary`:

1. **I · rss-coms** — extend the Protocol in `src/coms/interfaces/services.py`:
   ```python
   class KnowledgeProvider(Protocol):
       def brand_perception(self, brand: str) -> dict: ...
       def review_summary(self, product_id: str) -> dict: ...   # NEW
   ```
2. **P · rss-mplc** — implement it in `src/mplc/knowledge.py::BrandPerceptionProvider`
   (or add a new provider and `register("knowledge", "kg", ...)`; select via the
   marketplace `knowledge=` cfg).
3. **P · rss-usim** — probe it in `src/usim/choice_model.py`:
   `rs = knowledge.review_summary(slot.product_id)`.
4. **Verify** — `mplc/steel_thread --path knowledge`, then `--path system`.

> Contract (Recipe 2) vs interface (this one): use a **contract field** when the datum is
> cheap and every slot has it (ships on the page); use an **interface method** when it's
> a lookup the user pulls *on demand* (reviews, related items, a KG walk).

---

## Recipe 4 — Implement a bidding algorithm  *(1 service: rss-slrs; +1 if it needs new platform data)*

1. **P · rss-slrs** — edit `src/slrs/policy.py::SellerFleet.step` or branch on a new
   `strategy` name:
   ```python
   def step(self, round_idx, snapshot):
       if self.strategy == "pid_acos":
           target = 0.25
           for cid, c in self._controls.items():
               err = target - snapshot.get("seller_acos_mean", target)
               mult = min(2.0, max(0.5, c.bid_multiplier * (1 + 0.5 * err)))
               self._controls[cid] = replace(c, bid_multiplier=round(mult, 4))
       return list(self._controls.values())
   ```
   `step` returns `list[BidControls]`; the harness pushes them via `set_controls`. Bids
   live seller-side; the campaign lives on the platform (hosted model).
2. **W · config** — `SellerFleet` reads `strategy` from cfg; pass it through in
   `src/slrs/plugin.py` (already forwarded) and set it where the fleet is made, or add a
   `[sellers] strategy = "pid_acos"` key and thread it in `coms.harness.orchestrator`
   (the `seller_source` cfg dict).
3. **If your algorithm needs a signal the snapshot doesn't have** (e.g. per-campaign
   win-rate): that's a **2-service** change — add it to the marketplace snapshot in
   `rss-mplc/src/mplc/marketplace.py::snapshot` (drawing from `self.tracker`), then read
   it in `step`. `snapshot()` is the seller↔platform data contract each round.
4. **Verify** — `slrs/steel_thread --path campaign` (asserts bids move), then `--path system`.

---

## Recipe 5 — Add an auction mechanism  *(1 service: rss-mplc)*

1. **P · rss-mplc** — add a branch in `src/mplc/auction.py::run_auction` (e.g. `"vcg"`)
   computing `cpc` per winner.
2. **W · config** — `[[marketplaces]] mechanism = "vcg"`.
3. **Verify** — `mplc/steel_thread --path auction`.

---

## Recipe 6 — Add a metric  *(1–2 services)*

1. **P/health · rss-coms** — compute it in `src/coms/health/metrics.py::extract_metrics`
   (from the `UtilityLedger`) or in `src/coms/health/tracker.py` (per campaign).
2. **P · rss-mplc** (only if it needs marketplace-local state) — surface it in
   `marketplace.py::snapshot`.
3. It flows to `per_market` + the system aggregate automatically (numeric keys are
   summed in `coms.harness.orchestrator._aggregate`).
4. **Verify** — assert on it in `rss-coms/test/test_system.py`.

---

## Recipe 7 — Add a correlated-log event stage  *(1 service: rss-mplc)*

Any new touchpoint you want traceable:

1. **P · rss-mplc** — call `emit(party, stage, **fields)` inside `run_query` (helper
   already stamps `correlation_id` + `tick`). Use a `parent_id` if you want span chaining.
2. It lands in the shared `CorrelatedEventLog`; `coms.trace.timeline(cid)` picks it up
   with zero extra wiring.
3. **Verify** — `rss-coms/steel_thread --path trace` / a `timeline()` assertion.

---

## Recipe 8 — Run two services on separate nodes  *(W only)*

1. Start the marketplace as a server (its own process/node):
   ```python
   from coms.transport import serve_marketplace
   serve_marketplace(local_marketplace, host="0.0.0.0", port=8801)
   ```
2. **W · config** — point the harness at it:
   ```toml
   [[marketplaces]]
   id = "mkt"; plugin = "mplc"; transport = "http"; host = "10.0.0.7"; port = 8801
   ```
   `coms.transport.make_marketplace` returns a `RemoteMarketplace` for `transport="http"`.
   The `correlation_id` + rng state ride on every request, so metrics and the correlated
   timeline are identical to `inproc`.

> Distribution tip: keep the per-query seam (marketplace↔choice) co-located or batched;
> put the per-round seam (seller controls) or whole marketplaces on separate nodes.

---

## Recipe 9 — Toggle a topology  *(W only, no code)*

- **Two-party (search only):** `[sellers] enabled = false` → no fleet, `ad_slots=0`.
- **RTB instead of hosted:** `[[marketplaces]] ad_sourcing = "rtb"` → the marketplace calls
  the seller `BidderService.bid()` per request (`rss-slrs/src/slrs/bidder.py`).
- **Multiple marketplaces:** repeat the `[[marketplaces]]` block; per-market + aggregate
  metrics come back in the run result.

---

## New-capability checklist

1. Does data cross a service boundary? → add a **contract** (on-page datum) or an
   **interface method** (on-demand lookup) in `rss-coms`. Never a direct cross-party import.
2. Implement it in the owning party repo; **register** it in that repo's `plugin.py`.
3. If it's selectable, add a **config** key and thread it through
   `coms.harness.orchestrator` into the relevant `registry.make(...)` cfg.
4. Thread `rng`/`seed`; emit a correlated event if it's a new touchpoint.
5. Add a `steel_thread` path + a `test/` case in each touched repo; run
   `rss-coms/steel_thread --path system`.
6. Reinstall editable if you changed entry points: `pip install -e <repo>`.

## Map: file per concern

| Concern | File |
|---|---|
| Cross-service data shape | `rss-coms/src/coms/contracts/*` |
| Cross-service capability | `rss-coms/src/coms/interfaces/services.py` |
| Plugin registration / discovery | `rss-coms/src/coms/infra/registry.py` + each repo's `src/<pkg>/plugin.py` |
| Run loop / party resolution | `rss-coms/src/coms/harness/orchestrator.py` |
| Topology / node / mode selection | `system.toml` (`config/system.example.toml`) |
| Choice model | `rss-usim/src/usim/choice_model.py` |
| Personas / query gen | `rss-usim/src/usim/personas.py` |
| Search / ranking | `rss-mplc/src/mplc/search.py` |
| Auction mechanism / pricing | `rss-mplc/src/mplc/auction.py` |
| Hosted campaign registry | `rss-mplc/src/mplc/ads.py` |
| Knowledge provider | `rss-mplc/src/mplc/knowledge.py` |
| Marketplace seam / event emission / snapshot | `rss-mplc/src/mplc/marketplace.py` |
| Seller sampling / campaigns | `rss-slrs/src/slrs/{sellers,campaigns}.py` |
| Bidding / pacing | `rss-slrs/src/slrs/policy.py` |
| RTB bidder | `rss-slrs/src/slrs/bidder.py` |
| Metrics / welfare | `rss-coms/src/coms/health/*` |
| Correlated event log | `rss-coms/src/coms/trace/log.py` |
| Transport (cross-node) | `rss-coms/src/coms/transport/*` |
