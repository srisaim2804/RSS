# REPORT — Basic search system: components + A/B tests

Assignment: build a basic organic-search ranker for the `rss` simulator with all
four signal families — **lexical, semantic, behavioural, personalization** — and
A/B-test each one for a measurable gain.

Each step below is recorded in the same shape:

> **1. What & where** — the code that was added and the files it touched.
> **2. Results** — descriptive numbers, the bootstrap A/B test, and what it means.

The ranker lives in `rss-mplc/src/mplc/search.py` behind the `SearchIndex` seam
(`index(products)` / `search(query, k)`), selected by a new `search_index`
config key. Everything is **additive and off by default**: with
`search_index = "word_overlap"` (the default) every existing config, test and
steel-thread path behaves exactly as before.

> Earlier drafts `OVERALL.md` / `PROGRESS.md` / `ROUGH.md` describe a first
> click-log-only prototype (`ClickAwareSearchIndex`) that was never committed to
> these repos; this report supersedes them and tracks the full four-component
> build.

## Correction note (read this first)

An audit of the A/B harness (`experiments/_ab.py`) after the first pass of this
report found two bugs **in the evaluation code, not in the four repos' product
code** — the rankers being tested were always correct; the way they were being
measured wasn't. Both are fixed and every number below is regenerated:

1. **`organic_ctr` silently dropped sessions with zero organic impressions**
   instead of counting them as 0. ~45% of sessions never see an organic slot at
   all (organic starts at page position 3+, so `p_seen` is low there), and
   *which* sessions clear that bar is itself ranker-dependent — so the old
   metric compared control and treatment over different-sized, self-selected
   subpopulations (confirmed: sample sizes like 2192 vs. 2622 sessions for the
   "same" metric). Fixed to be unconditional over the same fixed population as
   every other metric (all ~4,000 sessions, every arm).
2. **The click-log CTR stats (`build_ctr_stats`) applied an inverse-propensity
   position correction that doesn't apply to this simulator.** The correction
   assumed clicked-given-seen probability depends on position, which is standard
   in real click logs — but in `usim/choice_model.py`, `p_click` is computed
   from relevance/rating/brand only, entirely independent of the `p_seen` draw,
   and the log only ever records a slot's outcome `if seen` in the first place.
   So the raw click rate among logged impressions was *already* an unbiased
   estimate of p(click | seen); the extra reweighting double-corrected and
   inflated every estimate (concretely: it drove the organic global CTR to the
   1.0 clip ceiling once ad impressions — whose shallow positions had been
   diluting the average — were correctly excluded). Fixed to plain smoothed
   click rate, organic impressions only.

Fixing (1) also **exposed a real, separate finding**: turning personalization on
changes two things at once (a wider candidate pool *and* a per-user reorder),
and most of its apparent CTR effect turns out to come from the pool-size change,
not the reordering. That's now measured directly — see S4.

Nothing in `rss-mplc`/`rss-coms`/`rss-usim`/`rss-slrs` changed for this
correction; the fix is entirely inside `experiments/_ab.py` and
`experiments/personalization_ab.py`. The four repos' test suites were re-run
and are unaffected.

---

## How to run

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ./rss-coms -e ./rss-usim -e ./rss-mplc -e ./rss-slrs pytest

# per-repo unit tests
cd rss-mplc && ../.venv/Scripts/python.exe -m pytest -q        # (repeat per repo)
# four-repo smoke
set PYTHONIOENCODING=utf-8 && .venv/Scripts/python.exe rss-coms/steel_thread/run.py --path system

# component A/B experiments (write experiments/data/*.json)
.venv/Scripts/python.exe experiments/semantic_ab.py      # S1
.venv/Scripts/python.exe experiments/bm25_ab.py          # S2
.venv/Scripts/python.exe experiments/behavioral_ab.py    # S3
.venv/Scripts/python.exe experiments/personalization_ab.py   # S4
.venv/Scripts/python.exe experiments/blend_sweep.py          # S5
```

`PYTHONIOENCODING=utf-8` works around a **pre-existing** Windows issue: every
repo's `steel_thread/run.py` prints a `→` (U+2192) that the default `cp1252`
console codec can't encode, so `test_steel_thread.py` shows 1–2 failures per repo
on Windows regardless of this work (confirmed by stashing all changes). All other
tests pass.

## A/B method (same for every step)

- **Control vs. treatment, identical `seed=0`** — the catalogue, users and seller
  campaigns are all seed-derived, so a shared seed is what makes the two arms
  like-for-like rather than two different worlds.
- World size (`experiments/_ab.py::BASE`): 20 rounds × 200 queries, 200 users,
  80 products, 15 sellers → **4,000 search sessions per arm**.
- **Descriptive**: aggregate metrics from `coms.health.extract_metrics`
  (purchases, revenue, welfare, mean campaign CTR) side by side.
- **Inferential**: four samples per search session — overall CTR, organic-only
  CTR, a 0/1 "did the user buy anything", and GMV/session (Σ price of purchases)
  — **all defined over the same fixed ~4,000-session population in every arm**
  (see Correction note) — fed to `coms.health.compare_arms` (2,000-resample
  percentile bootstrap, 95% CI). A result counts as a **gain only if the CI
  excludes 0**.

## Scoreboard

| Step | Component | Reorders results? | Significant gain vs. its control? |
|---|---|---|---|
| S1 | Semantic (lexical + LSA cosine) | Yes (proven) | **No** — every 95% CI straddles 0 |
| S2 | Lexical baseline (BM25 vs. overlap) | Yes (proven) | **No** — organic CTR +1.20 pp (CI [−0.35, +2.79]); welfare −7.5% |
| S3 | Behavioural (click-log CTR re-rank) | Yes (proven) | **No** — but the best-behaved single component: overall CTR +0.87 pp (ns), welfare **+13.3%**, purchases flat |
| S4 | Personalization (per-user re-rank) | Yes (proven) | **Real, but not what it first looked like** — decomposed: pool-widening alone causes a *significant* CTR drop with **zero** purchase gain; the actual re-ranking (pool size held fixed) is CTR-neutral and drives **100% of the +52 purchases** |
| S5 | Blended ranker + weight sweep | Yes | **No significant win.** Best risk-adjusted point: `behavioral` at a *lighter* weight (`ctr_weight≈0.3`) than S3's default — CTR leans positive (ns), welfare +$2.4k, no CI reaches significant-negative |

---

## S1 — Semantic component

### 1. What & where

| File | Change |
|---|---|
| `rss-mplc/src/mplc/search.py` | **New `SemanticSearchIndex`.** `index()` builds a TF-IDF term–document matrix over product titles and reduces it with a truncated SVD (`numpy.linalg.svd`, default `n_components=16`) → LSA. `search()` keeps the **same candidate set** a word-overlap search returns (`overlap > 0`) but orders it by `(1 − sem_weight)·overlap + sem_weight·cosine`, where `cosine` is the query/title similarity in the latent space (`sem_weight` default `0.5`). The `relevance` value returned for each hit is the **pure token overlap**, never the cosine, so the semantic signal only changes slot order and can't inflate its own downstream `p_click`. Also added `_tokenize()` and two `register("search_index", …)` calls (`"word_overlap"` → the existing `MockSearchIndex`, `"semantic"` → the new class). `MockSearchIndex`: unchanged. |
| `rss-mplc/src/mplc/marketplace.py` | `Marketplace.__init__` gained `search_index: str = "word_overlap"` and `search_index_cfg: dict \| None`. The hard-coded `self._search = MockSearchIndex()` became a registry lookup (`_make_component("search_index", {"name": …, **cfg})`) with a `except KeyError: MockSearchIndex()` fallback — the same pattern as the `knowledge` backend right below it. Every caller that doesn't pass the new args gets byte-identical behaviour. |
| `rss-mplc/src/mplc/plugin.py` | `from . import search` (so its `register` calls fire), and forwards `search_index` / `search_index_cfg` from the marketplace config dict into `Marketplace(...)`. |
| `rss-coms/src/coms/harness/orchestrator.py` | Threads `search_index` / `search_index_cfg` from a `[[marketplaces]]` block into the `registry.make("marketplace", …)` call — the one change outside `rss-mplc`, needed because the harness allowlists which config keys reach the marketplace factory. |
| `rss-coms/config/system.example.toml` | Documents `search_index = "word_overlap"` and a commented `search_index_cfg` example. |
| `rss-mplc/test/test_mplc.py` | 3 new tests: semantic returns the **same candidate set** as word-overlap and reports **pure-overlap `relevance`**; `sem_weight=0` reproduces the word-overlap order exactly; `Marketplace(search_index="semantic", …)` wires up and runs a full query end to end. |
| `experiments/_ab.py`, `experiments/semantic_ab.py` | New, outside all four repos. `_ab.py` = the shared A/B harness (run an arm, flatten the event log to per-session samples). `semantic_ab.py` = this step's control/treatment run, descriptive + bootstrap comparison, concrete reorderings; writes `experiments/data/semantic_ab.json`. |

**Verification:** `rss-mplc` `test/test_mplc.py` 10/10 pass; four-repo
`steel_thread --path system` OK; the only red tests are the pre-existing
`cp1252`/`→` steel-thread failures, present with all changes stashed.

### 2. Results

**It reorders results — proven.** Top-5, `word_overlap → semantic`, same catalogue:

```
'mechanical'         [P00000,P00005,P00006,P00011,P00012] → [P00048,P00062,P00050,P00029,P00074]
'headphones'         [P00001,P00006,P00014,P00018,P00023] → [P00018,P00057,P00023,P00047,P00042]
'portable monitor'   [P00002,P00062,P00006,P00007,P00011] → [P00062,P00002,P00075,P00018,P00011]
```

On short queries many products tie at `overlap = 1.0`; word-overlap then breaks
ties by `product_id` (arbitrary), while semantic breaks them by latent-topic
similarity — a real, non-trivial change to what lands in the top slots.

**Descriptive (aggregate, 4,000 sessions/arm):**

| metric | word_overlap | semantic | Δ |
|---|---|---|---|
| purchases | 741 | 667 | −74 |
| platform revenue | 11,576.58 | 11,701.86 | +125.29 |
| seller profit | 22,693.87 | 21,592.82 | −1,101.06 |
| total welfare | 34,270.45 | 33,294.68 | −975.77 |
| mean campaign CTR | 0.5681 | 0.5665 | −0.0016 |
| per-session CTR (mean) | 52.12% | 51.92% | −0.20% |
| organic CTR (mean, unconditional) | 19.45% | 20.11% | +0.65% |

(`user surplus / session` is structurally 0 in this simulator — the choice
model's surplus term `max(0, price·(0.6+0.08·rating) − price)` is ≤ 0 for every
rating in `[3,5]` — so welfare ≈ platform revenue + seller profit.)

**Inferential (bootstrap A/B, 95% CI, semantic − word_overlap):**

| sample | ATE | 95% CI | significant? |
|---|---|---|---|
| per-session overall CTR | **−0.20 pp** | [−1.54, +1.16] pp | **No** |
| per-session organic CTR | **+0.65 pp** | [−1.00, +2.30] pp | **No** |
| per-session any-purchase | **−1.43 pp** | [−3.10, +0.18] pp | **No** |
| GMV / session | **−0.73** | [−3.43, +2.11] | **No** |

**Bottom line: no gain.** Every interval contains 0.

**Why (and why it's the expected result here):** in this simulator the choice
model sets `p_click ≈ 0.04 + 0.5·relevance` and `relevance` **is** the token-overlap
score — exactly, no noise. So word-overlap order is already close to
click-probability order. Semantic re-ranking only shuffles items *within* an
equal-overlap tier, and the LSA cosine is decorrelated from what actually
separates those items for a user (rating, brand trust, price fit) — so it behaves
as noise on the graded metric. A semantic signal earns its keep when the lexical
relevance signal is itself imperfect or incomplete; that isn't the case in this
toy world, where relevance is handed to the ranker by construction. The behavioural
(S3) and personalization (S4) components target signals the choice model *does*
use beyond overlap, so they are where a real gain is plausible.

---

## S2 — Lexical baseline (BM25 vs. token overlap)

Does a stronger *lexical* scorer alone move the metrics, before any behavioural or
personalization signal is layered on? Control = the existing `word_overlap`
(`|q ∩ t| / |q|`, every matched token equal, divided by query length).
Treatment = Okapi BM25 (`k1 = 1.5`, `b = 0.75`): idf-weights rare query terms and
normalises by title length.

### 1. What & where

| File | Change |
|---|---|
| `rss-mplc/src/mplc/search.py` | **New `BM25SearchIndex`.** `index()` builds per-title term counts, document lengths, `avgdl`, and `idf[t] = ln(1 + (N − df + 0.5)/(df + 0.5))`. `search()` keeps the **same candidate set** as `word_overlap` (title shares ≥ 1 query token) and orders it by the standard BM25 sum `Σ idf(t)·f·(k1+1)/(f + k1·(1 − b + b·dl/avgdl))`; **reported `relevance` stays pure token overlap**. Registered as `search_index = "bm25"` (`k1`/`b` via `search_index_cfg`). Added `import math`. |
| `rss-mplc/test/test_mplc.py` | 3 new tests: bm25 returns the **same candidate set** as word-overlap and reports **pure-overlap `relevance`**; a hand-built catalogue where two products tie on overlap but one matches a rare (high-idf) term proves **bm25 promotes the rare-term match** where word-overlap just tie-breaks on `product_id`; `Marketplace(search_index="bm25", …)` wires up and runs end to end. |
| `experiments/_ab.py` | Factored the S1 comparison logic into reusable helpers — `compare()` (descriptive Δ + `compare_arms` bootstrap for all four samples), `print_compare()`, `reorder_examples()`. |
| `experiments/bm25_ab.py` | New. Control/treatment run + comparison; writes `experiments/data/bm25_ab.json`. |

**Verification:** `rss-mplc` `test/test_mplc.py` 13/13 pass; four-repo
`steel_thread --path system` OK; same pre-existing `cp1252`/`→` steel-thread
failures only.

### 2. Results

**It reorders results — proven.** Top-5, `word_overlap → bm25`, same catalogue:

```
'mechanical'       [P00000,P00005,P00006,P00011,P00012] → [P00048,P00050,P00011,P00029,P00038]
'headphones'       [P00001,P00006,P00014,P00018,P00023] → [P00018,P00023,P00057,P00001,P00042]
'portable monitor' [P00002,P00062,P00006,P00007,P00011] → [P00062,P00002,P00007,P00018,P00022]
```

For broad queries where overlap saturates at 1.0 across many items, BM25 actually
orders that tier — a title that is *just* the query terms outranks one that
buries them among others — instead of falling back to `product_id`.

**Descriptive (aggregate, 4,000 sessions/arm):**

| metric | word_overlap | bm25 | Δ |
|---|---|---|---|
| purchases | 741 | 700 | −41 |
| platform revenue | 11,576.58 | 11,777.26 | +200.68 |
| seller profit | 22,693.87 | 19,939.36 | −2,754.51 |
| total welfare | 34,270.45 | 31,716.62 | −2,553.83 |
| mean campaign CTR | 0.5681 | 0.5734 | +0.0053 |
| per-session CTR (mean) | 52.12% | 52.78% | +0.66% |
| organic CTR (mean, unconditional) | 19.45% | 20.65% | +1.20% |

**Inferential (bootstrap A/B, 95% CI, bm25 − word_overlap):**

| sample | ATE | 95% CI | significant? |
|---|---|---|---|
| per-session overall CTR | **+0.66 pp** | [−0.77, +2.06] pp | **No** |
| per-session organic CTR | **+1.20 pp** | [−0.35, +2.79] pp | **No** |
| per-session any-purchase | **−1.30 pp** | [−2.88, +0.25] pp | **No** |
| GMV / session | **−0.89** | [−3.61, +1.98] | **No** |

**Bottom line: no confirmed gain.** BM25 pushes CTR — especially **organic** CTR,
the metric a pure lexical change should touch — in the right direction, but the
CI still includes 0. It also carries a real cost: seller profit and total welfare
drop ~7.5% (bm25 promotes different items into the top organic slots, and the
ones it favours convert to lower-value purchases), though `any_purchase` isn't
significant either.

**Interpretation:** BM25 is a better *lexical* relevance proxy than the overlap
fraction, and the direction of the CTR effect confirms that. But in this
simulator the reported `relevance` (hence `p_click`) is held at pure overlap by
design, so BM25 can only help by getting *which* equal-overlap item sits in a
high-`p_seen` slot slightly more right — a small, noisy effect. Kept as an
available baseline; `word_overlap` remains the canonical control for S3–S5 since
BM25's advantage is unconfirmed.

---

## S3 — Behavioural component (click-log CTR re-rank)

The first component that targets a click driver the choice model uses *beyond*
overlap: `p_click` also carries per-item rating and brand-trust terms, which a
product's historical CTR captures and word overlap can't see. Control =
`word_overlap` (this run also collects the log). Treatment = `behavioral`: sort
by `(1 − ctr_weight)·overlap + ctr_weight·ctr_signal`, `ctr_weight = 0.5`.

### 1. What & where

| File | Change |
|---|---|
| `rss-mplc/src/mplc/search.py` | **New `ClickAwareSearchIndex`** + `load_click_stats(path)`. `search()` keeps the `word_overlap` candidate set and blends in a historical CTR signal looked up **(query,item) → item → global mean**; **reported `relevance` stays pure token overlap** (a well-clicked item gets a better slot / higher `p_seen`, but its `p_click`-given-seen is unchanged — the signal can't grade its own homework). Registered as `search_index = "behavioral"`; takes `ctr_weight` and either an in-memory `stats` dict or a `stats_path` JSON. Added `import json`. |
| `rss-mplc/test/test_mplc.py` | 5 new tests: same candidate set + pure-overlap `relevance`; **no stats ⇒ identical order to `word_overlap`** (invariant); a high-CTR item **overtakes** an equal-overlap rival when `ctr_weight` is high; **`relevance` stays `overlap` even when a product's stored CTR is 1.0** (circularity guard); `Marketplace(search_index="behavioral", …)` wires up and runs end to end. |
| `experiments/_ab.py` | **New `build_ctr_stats(log)`** — smoothed click-through-rate tables from an event log, **organic impressions only** (sponsored impressions get an `ad_susceptibility` click boost unrelated to organic relevance, so they're excluded to avoid contaminating the organic ranking signal). No position/propensity reweighting is applied — see the Correction note for why that would be wrong here. Each key is additively smoothed toward the organic global mean (`k = 10`) and clipped to `[0, 1]`. Also added a 4th per-session sample, **GMV/session** (Σ price of purchases). |
| `experiments/behavioral_ab.py` | New. Runs control, builds the CTR tables from the control log, runs the treatment reading them, compares; writes `experiments/data/ctr_stats.json` + `behavioral_ab.json`. |

**Verification:** `rss-mplc` `test/test_mplc.py` 18/18 pass; four-repo
`steel_thread --path system` OK; same pre-existing `cp1252`/`→` failures only.

### 2. Results

CTR tables built from 2,731 **organic** impressions (64 items, 465 distinct
`(query,item)` pairs), raw/global organic CTR 35.55%.

**It reorders results — proven** (`word_overlap → behavioral`, same catalogue):

```
'mechanical'      [P00000,P00005,P00006,P00011,P00012] → [P00048,P00012,P00029,P00011,P00006]
'headphones'      [P00001,P00006,P00014,P00018,P00023] → [P00014,P00042,P00031,P00006,P00018]
```

The moves are smaller than S1/S2's: this simulator's per-item CTR spread beyond
overlap is genuinely narrow (rating moves `p_click` only ±5%/point), so the
behavioural signal's *marginal* information over overlap is small.

**Descriptive (aggregate, 4,000 sessions/arm):**

| metric | word_overlap | behavioral | Δ |
|---|---|---|---|
| purchases | 741 | 740 | −1 |
| platform revenue | 11,576.58 | 11,817.90 | +241.32 |
| seller profit | 22,693.87 | 27,002.09 | **+4,308.22** |
| total welfare | 34,270.45 | 38,819.99 | **+4,549.54 (+13.3%)** |
| mean campaign CTR | 0.5681 | 0.5739 | +0.0058 |
| per-session CTR (mean) | 52.12% | 52.99% | +0.87% |
| organic CTR (mean, unconditional) | 19.45% | 19.55% | +0.09% |

**Inferential (bootstrap A/B, 95% CI, behavioral − word_overlap):**

| sample | ATE | 95% CI | significant? |
|---|---|---|---|
| per-session overall CTR | **+0.87 pp** | [−0.47, +2.29] pp | **No** |
| per-session organic CTR | **+0.09 pp** | [−1.52, +1.73] pp | **No** |
| per-session any-purchase | **−0.08 pp** | [−1.73, +1.50] pp | **No** |
| GMV / session | **+1.58** | [−1.33, +4.37] | **No** |

**Bottom line: no statistically confirmed gain — but the best-behaved component
so far.** It leans positive on overall CTR and GMV, purchases are essentially
unchanged (−1 out of 741), and its welfare/profit move is by far the largest of
any step (**+13.3%**) and in the *right* direction (BM25's was −7.5%). Every CI
still contains 0, so it's not a win on its own — but it's the strongest single
candidate for the S5 blend.

---

## S4 — Personalization (per-user organic re-rank)

The first component that uses the *user*. `SearchIndex.search(query, k)` has no
user argument, so personalization runs one layer up, in
`marketplace.py::run_query`: over-fetch an organic candidate pool from whatever
ranker is configured, re-rank it per user, then fill the slots.

**This step's A/B needed a redesign.** A naive control (`personalize="off"`,
which fetches exactly `organic_slots` candidates) vs. treatment
(`personalize="rules"`, which fetches `4× organic_slots` to leave room to
reorder) changes **two things at once**: the reordering *and* the candidate
pool size. A wider pool independently fills more organic slots per session
(fewer collide with ad picks), which mechanically raises organic-impression
counts regardless of whose items get promoted. To isolate the real effect, this
step runs **three** arms:

- **A — baseline**: `behavioral` ranker (from S3, `ctr_weight=0.5`), `personalize="off"` (narrow pool).
- **B — pool-only**: same ranker, `personalize="rules"` with `weight=0.0` — a **verified identity reorder** (`RulePersonalizer`'s base score `1 − rank/pool_size` is already strictly monotonic in rank, so `weight=0` reproduces the ranker's own order exactly) that still fetches the wide pool. This isolates the pool-size effect alone.
- **C — full**: same ranker, `personalize="rules"`, `weight=0.5` — the real thing.

`B − A` = pool-widening effect. `C − B` = pure re-ranking effect, pool size held
fixed. `C − A` = total effect (what naively "turning personalization on" looks
like).

### 1. What & where

| File | Change |
|---|---|
| `rss-mplc/src/mplc/personalize.py` | **New module.** `NoPersonalizer` (identity, default) and `RulePersonalizer`. The rule assigns each pool candidate `base = 1 − rank/pool_size` and adds `weight · bonus(user, product)`, then re-sorts (ties keep ranker order). `bonus ∈ [−1, 1]` = `0.5·price_term + 0.3·brand_term + 0.2·rating_term`, where **price_term** rewards cheaper items for price-sensitive / bargain users and pricier items for the `premium` segment, **brand_term** = `brand_loyalty · (trust − 0.5)·2` (trust from `brand_perception`), **rating_term** = `(review_dependency/10)·(rating − 3)/2`. Registered under a new `personalizer` family (`"off"` / `"rules"`). |
| `rss-mplc/src/mplc/marketplace.py` | `__init__` gained `personalize` / `personalize_cfg`; builds `self._personalizer` from the registry (fallback `NoPersonalizer`). In `run_query`, when personalization is on: fetch `4 × organic_slots` candidates, `reorder(user, hits, self.brand_perception)`, then fill up to `organic_slots`. When `"off"`: fetch exactly `organic_slots` and skip the reorder — **byte-identical to before** (asserted by a test). Reported `relevance` is still pure overlap. |
| `rss-mplc/src/mplc/plugin.py`, `rss-coms/src/coms/harness/orchestrator.py`, `rss-coms/config/system.example.toml` | Thread `personalize` / `personalize_cfg` through, same pattern as `search_index`. |
| `rss-mplc/test/test_mplc.py` | 6 new tests: `off` is identity; a **bargain** user pulls the cheapest candidate to the top, a **premium** user the priciest (large weight); at the default weight the bonus **only perturbs** — it can't lift the last candidate past a relevant first one; `personalize="off"` reproduces the plain-`Marketplace` slot order exactly; `Marketplace(personalize="rules", …)` wires up and returns ≤ `organic_slots` organic slots. |
| `experiments/personalization_ab.py` | Rewritten to run the A/B/C decomposition above and report all three pairwise comparisons, plus a per-segment re-rank demo (bargain vs. premium on the same pool). |

**Verification:** `rss-mplc` `test/test_mplc.py` 24/24 pass; four-repo
`steel_thread --path system` OK; same pre-existing `cp1252`/`→` failures only.
`RulePersonalizer(weight=0.0)` reproduces the input order exactly, checked directly.

### 2. Results

**It reorders results per user — proven.** Same query, same ranker pool
(`id, price`), re-ranked for two users:

```
'gaming mouse'  ranker : [P00033 $257, P00013 $16,  P00021 $169, P00050 $74,  P00065 $238]
                bargain: [P00013 $16,  P00050 $74,  P00021 $169, P00033 $257, P00028 $86 ]
                premium: [P00033 $257, P00021 $169, P00013 $16,  P00065 $238, P00045 $287]
```

The bargain user's slate is pulled toward the cheap items; the premium user's
stays on the pricier ones.

**Descriptive (aggregate, 4,000 sessions/arm):**

| metric | A baseline | B pool-only | C full |
|---|---|---|---|
| purchases | 740 | 740 | **792** |
| platform revenue | 11,817.90 | 11,612.08 | 11,712.05 |
| seller profit | 27,002.09 | 21,503.45 | 20,737.51 |
| total welfare | 38,819.99 | 33,115.53 | 32,449.56 |
| mean campaign CTR | 0.5739 | 0.5698 | 0.5651 |
| overall CTR (mean) | 52.99% | 49.91% | 50.46% |
| organic CTR (mean) | 19.55% | 22.18% | 23.32% |

**Inferential (bootstrap A/B, 95% CI):**

| comparison | overall CTR | organic CTR | any-purchase | GMV/session |
|---|---|---|---|---|
| **B − A** (pool-widening alone) | **−3.08 pp [−4.52,−1.67] · sig** | **+2.64 pp [+0.97,+4.31] · sig** | +0.28 pp [−1.35,+1.88] ns | −1.28 [−4.13,+1.60] ns |
| **C − B** (pure re-ranking, pool fixed) | +0.55 pp [−0.79,+1.92] ns | +1.14 pp [−0.59,+2.77] ns | +0.85 pp [−0.73,+2.40] ns | +0.68 [−2.11,+3.30] ns |
| **C − A** (total, naive "on/off") | **−2.53 pp [−3.86,−1.20] · sig** | **+3.77 pp [+2.18,+5.46] · sig** | +1.12 pp [−0.50,+2.82] ns | −0.60 [−3.41,+2.22] ns |

**Bottom line: the headline "personalization moves CTR" effect is mostly a pool-size
artifact, not the reordering logic — and the actual purchase gain comes entirely
from the reordering, not the pool.**

- **B − A isolates the pool-size effect alone** (identity reorder, wider pool):
  overall CTR drops **significantly** (−3.08 pp) and organic CTR rises
  **significantly** (+2.64 pp) — with **zero** purchase gain (740 → 740) and a
  **worse** welfare number (−$5.7k). A wider candidate pool fills more organic
  slots per session (fewer lost to ad-id collisions); average organic
  impressions/session measured directly at 0.69 → 0.96 (+39%). More organic
  slots filled mechanically pulls the *unconditional* organic-CTR mean up (more
  sessions contribute a nonzero ratio instead of 0) while displacing higher-CTR
  ad exposure, pulling overall CTR down. **None of this is about which item gets
  promoted.**
- **C − B isolates the actual per-user reordering**, pool size held fixed: CTR
  effects shrink to non-significant and flip mildly *positive* (+0.55 pp
  overall, +1.14 pp organic), and **this is where all 52 of the +52 total
  purchases come from** (740 → 792, entirely within B→C; A→B contributed 0).
  Welfare cost here is much smaller than the naive total suggested (−$0.7k vs.
  the naive −$6.4k A→C figure once you don't also blame the pool effect on it).
- **C − A (the number a naive on/off test would report)** is a mix of both:
  significant CTR loss, significant organic-CTR gain, +52 purchases — technically
  correct as a top-line, but attributing it to "personalization reorders toward
  price-fit items, trading clicks for conversions" is only true of the `C − B`
  slice. A meaningful share of the naive CTR loss would happen even with a
  no-op personalizer, purely from widening the pool.

**Practical takeaway:** if personalization ships, the pool-widening side effect
should either be accepted as a deliberate, separate "wider retrieval pool"
feature (and A/B'd on its own terms — here it's a net negative: significant CTR
loss, no purchase gain, worse welfare) or engineered out (reorder within the
original, narrower candidate set rather than over-fetching). The re-ranking
logic itself, isolated, is a small, non-significant, purchase-positive,
CTR-neutral change — a much more modest and more defensible result than the
original "−1.94pp CTR, +93 purchases" headline implied.

---

## S5 — Blended ranker + weight sweep (the ablation ladder)

All four signal families in one tunable object, swept as a grid, every cell
A/B'd against the **same** control (`word_overlap`, `personalize="off"`). Note:
every arm below that includes `personalize="rules"` inherits the **same
pool-widening confound quantified in S4** — its CTR/organic-CTR numbers mix the
pool effect with the reordering effect, exactly as the naive `C − A` comparison
did there.

### 1. What & where

| File | Change |
|---|---|
| `rss-mplc/src/mplc/search.py` | **New `BlendedSearchIndex`** (`search_index = "blended"`): sort key `= (w_overlap·overlap + w_semantic·cosine + w_ctr·ctr) / Σw` over the lexical candidate set; reported `relevance` stays pure overlap. It **composes the existing pieces** — a `SemanticSearchIndex` for the cosine term (only built when `w_semantic > 0`), a `ClickAwareSearchIndex` for the CTR term — so `word_overlap`, `semantic` and `behavioral` are all special cases of it (a test asserts the `behavioral` equivalence). Also refactored `SemanticSearchIndex` to expose `cosine(query) → {product_id: sim}`, now shared by its own `search()` and the blend. |
| `rss-mplc/src/mplc/plugin.py`, `orchestrator.py`, `system.example.toml` | `blended` registered; `w_overlap`/`w_semantic`/`w_ctr`/`stats_path` documented. |
| `rss-mplc/test/test_mplc.py` | 5 new tests: overlap-only blend == `word_overlap`; CTR term promotes a high-CTR item; **blend with `w_overlap=w_ctr` reproduces `behavioral` exactly**; `Marketplace(search_index="blended", …)` wires end to end; `SemanticSearchIndex.cosine` returns an in-range map over all indexed products. |
| `experiments/blend_sweep.py` | One control run (+ CTR-stats build), then 8 arms: the ladder (semantic → behavioural at `t ∈ {0.3, 0.6, 0.9}` → + personalization at `{0.25, 0.5}`) plus two "all signals on" points. Emits a trade-off table + an auto-recommendation (best any-purchase ATE among arms whose CTR 95% CI lower bound ≥ −1 pp). |

**Verification:** `rss-mplc` `test/test_mplc.py` 29/29 pass; four-repo
`steel_thread --path system` OK; same pre-existing `cp1252`/`→` failures only.

### 2. Results

Δ vs. `word_overlap` control (4,000 sessions/arm; CTR / any-purchase in pp with
95% CI; `Δ purch` / `Δ welfare` are aggregate):

| arm | Δ overall CTR (pp) | Δ organic CTR (pp) | Δ any-purchase (pp) | Δ purch | Δ welfare |
|---|---|---|---|---|---|
| L1  semantic (`w_s=0.5`) | −0.20 [−1.54,+1.16] | +0.65 [−1.00,+2.30] | −1.43 [−3.10,+0.18] | −74 | −976 |
| L2  behavioural `t=0.3` | +1.07 [−0.29,+2.40] | +0.78 [−0.92,+2.44] | −0.20 [−1.82,+1.43] | −14 | **+2,431** |
| L2  behavioural `t=0.6` | +0.47 [−0.94,+1.79] | −0.07 [−1.80,+1.53] | −0.95 [−2.62,+0.63] | −43 | +1,753 |
| L2  behavioural `t=0.9` | **−2.43 [−3.89,−1.08] · sig** | −0.65 [−2.29,+0.97] | +0.45 [−1.22,+2.15] | +21 | **+3,509** |
| L3  beh `0.6` + personal `0.25` | **−1.82 [−3.23,−0.47] · sig** | **+2.80 [+1.07,+4.42] · sig** | +1.00 [−0.65,+2.57] | +42 | −1,071 |
| L3  beh `0.6` + personal `0.50` | **−1.83 [−3.21,−0.53] · sig** | **+3.13 [+1.54,+4.84] · sig** | +1.42 [−0.25,+3.10] | +67 | −295 |
| FULL `w_o=.45 w_s=.15 w_c=.4`, no personal | −0.02 [−1.40,+1.33] | +0.71 [−1.01,+2.38] | −0.18 [−1.80,+1.38] | −8 | +2,089 |
| FULL + personal `0.35` | **−1.85 [−3.19,−0.47] · sig** | **+3.27 [+1.63,+5.08] · sig** | +0.25 [−1.45,+1.85] | +11 | −444 |

**What the ladder shows:**

1. **Semantic adds nothing** (confirms S1), at any rung.
2. **Behavioural has a sweet spot at *low* weight, and it's better than S3's
   own default.** `t=0.3` is the best risk-adjusted single arm in the table: CTR
   leans *positive* (not significant), no CI reaches significant-negative, and
   welfare is the second-best in the sweep (+$2.4k). Pushing the weight to
   `t=0.9` **significantly hurts** CTR (−2.43 pp) even though its aggregate
   welfare happens to be highest (+$3.5k) — a reminder that a significant CTR
   loss can still coexist with a welfare gain if the purchases it does produce
   are higher-value.
3. **Every arm with personalization shows the same S4 signature**: significant
   CTR loss + significant organic-CTR gain, both substantially inflated by the
   pool-widening confound quantified in S4 rather than purely the reordering.
4. **`FULL` (all three lexical/semantic/behavioural signals, no personalization)
   is CTR-neutral (−0.02 pp) with solid welfare (+$2.1k) but no longer clears the
   sweep's own −1 pp CTR safety bar** on its confidence interval (lower bound
   −1.40) — so the auto-recommendation now prefers the simpler, lighter-touch
   `L2 behavioural t=0.3` over the "everything blended" point.

**Auto-recommendation from the sweep:** `L2 behavioural t=0.3` — i.e. plain
`search_index="behavioral"` with `ctr_weight≈0.3` (lighter than the `0.5` used
as S3's headline number), personalization off.

---

## Conclusion — recommended configuration

```toml
[[marketplaces]]
search_index = "behavioral"
search_index_cfg = { ctr_weight = 0.3, stats_path = "experiments/data/ctr_stats.json" }
personalize = "off"          # see below before turning this on
```

- **A light behavioural blend (`ctr_weight≈0.3`) on top of plain lexical
  overlap is the safest, best-supported single change**: CTR leans positive
  (not significant), welfare is up substantially, and no confidence interval on
  any metric reaches significant-negative. Semantic adds nothing measurable and
  can be left out or kept at a small weight for completeness; a heavier
  behavioural weight (`t≥0.9`) starts to significantly hurt CTR.
- **Personalization is a real but entangled lever, not a clean toggle.** Once
  decomposed (S4), its own re-ranking logic is small, CTR-neutral, and
  purchase-positive — but as currently implemented it also over-fetches a wider
  candidate pool, and *that alone* significantly hurts CTR with zero purchase
  benefit. Before enabling it in production, either accept and separately
  justify the pool-widening side effect, or change the implementation to
  reorder within the original candidate window instead of a wider one.
- **Why no component is a significant standalone win:** this simulator sets
  `p_click ≈ 0.04 + 0.5·relevance` with `relevance` == the token-overlap score,
  exactly and without noise, so the baseline ranker is already near
  click-optimal. The methodology (per-session bootstrap A/B on 4 metrics over a
  fixed population, shared seed, honest circularity guards, a pool-vs-reorder
  decomposition where the naive comparison was confounded) is the transferable
  result; against the Docker grader — which ships real embeddings, a real BM25
  index and an imperfect relevance signal — the same ranker family has genuine
  headroom to beat the random / BM25 / semantic baselines.
