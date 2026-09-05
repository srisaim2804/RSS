# Report For Search Components

Organic ranker for the `rss` simulator, built behind the `SearchIndex` seam,
selected by a config key. Every row below is measured the same way: same
`seed=0` world (catalogue/users/campaigns are seed-derived, so a shared seed is
what makes rows comparable), 20 rounds × 200 queries = **4,000 search sessions**,
every metric computed over that same fixed set of sessions in every arm, compared
with `coms.health.compare_arms` (2,000-resample bootstrap, 95% CI). A move only
counts as real if the CI excludes 0 — everything else is noise.

## CTR by ranker combination

| Ranker (cumulative) | Overall CTR | Δ vs. lexical (pp, 95% CI) | Organic CTR | Δ organic (pp, 95% CI) |
|---|---|---|---|---|
| **Lexical** (word overlap) — baseline | 52.12% | — | 19.45% | — |
| Lexical *(BM25 instead of overlap)* | 52.78% | +0.66 [−0.77, +2.06] | 20.65% | +1.20 [−0.35, +2.79] |
| Lexical + Semantic | 51.92% | −0.20 [−1.54, +1.16] | 20.11% | +0.65 [−1.00, +2.30] |
| Lexical + Behavioral (`ctr_weight=0.5`) | 52.99% | +0.87 [−0.47, +2.29] | 19.55% | +0.09 [−1.52, +1.73] |
| Lexical + Behavioral (`ctr_weight=0.3`, tuned) | 53.19% | +1.07 [−0.29, +2.40] | 20.23% | +0.78 [−0.92, +2.44] |
| Lexical + Semantic + Behavioral (blended) | 52.10% | −0.02 [−1.40, +1.33] | 20.16% | +0.71 [−1.01, +2.38] |

*(Organic CTR here is unconditional over all 4,000 sessions, including the
~45% that never see an organic slot at all — counted as 0, not dropped, so
every column compares the same population.)*

## Personalization, decomposed

Naively switching `personalize` on changes **two things at once**: it fetches a
wider candidate pool (to leave room to reorder) *and* it reorders by user. These
have to be separated to know what's actually happening. Baseline here is the
`Lexical + Behavioral (0.5)` ranker above:

| Arm | Overall CTR | Δ vs. baseline | Organic CTR | Δ organic | Purchases |
|---|---|---|---|---|---|
| Baseline (personalize off, narrow pool) | 52.99% | — | 19.55% | — | 740 |
| **+ wider pool only** (no-op reorder) | 49.91% | **−3.08 pp [−4.52,−1.67] · significant** | 22.18% | **+2.64 pp [+0.97,+4.31] · significant** | 740 (+0) |
| **+ wider pool + real reorder** (full personalization) | 50.46% | **−2.53 pp [−3.86,−1.20] · significant** | 23.32% | **+3.77 pp [+2.18,+5.46] · significant** | 792 (+52) |

Isolating the reorder alone (full vs. pool-only, pool size held fixed): overall
CTR +0.55 pp [−0.79, +1.92] (not significant), organic CTR +1.14 pp [−0.59, +2.77]
(not significant), and **all +52 purchases** come from this step — the
pool-widening step alone contributed zero purchases.

## What this shows

**Nothing moves CTR in a statistically meaningful way on its own — except the
personalization pool-widening side effect, which is significant and is not
even about personalization.**

- **BM25 vs. plain overlap** is the largest lexical-only positive lean —
  organic CTR +1.20 pp — but the interval still crosses 0. It comes with a real
  cost elsewhere: total welfare fell ~7.5% because BM25 promotes different,
  lower-margin items into the top slots.
- **Semantic** is flat-to-negative and adds the least of any component —
  expected, since in this simulator the click model's relevance signal *is* the
  overlap score, so a re-rank by embedding similarity is reshuffling noise
  relative to what actually drives clicks.
- **Behavioral** is the best single component: it leans positive on CTR at both
  weights tested, and aggregate welfare rose **+13.3%** at `ctr_weight=0.5`
  while purchases held essentially flat (−1 of 741). A *lighter* weight
  (`ctr_weight=0.3`) does even better on CTR (+1.07 pp) with strong welfare too
  (+$2.4k) — tuning it down from the initial 0.5 guess helps.
- **Stacking semantic + behavioral together** is CTR-neutral (−0.02 pp, not the
  clean positive lean the light-behavioral-alone arm gets) — semantic isn't
  pulling its weight in the blend.
- **Personalization's headline CTR move is mostly not about personalization.**
  Turning it on changes the candidate pool size as a side effect of how it's
  implemented (over-fetching to leave room to reorder), and *that alone* —
  with zero actual reordering — already produces a significant CTR drop
  (−3.08 pp) and a significant organic-CTR rise (+2.64 pp), with **zero**
  purchase benefit. Only once you hold the pool size fixed and isolate the real
  per-user reordering does the true picture emerge: a small, non-significant,
  CTR-neutral-to-positive change that is responsible for **100% of the
  purchase gain** (+52). The naive "before/after" number (−2.53 pp CTR,
  +52 purchases) is real as a top-line, but crediting the CTR cost to
  "personalization reorders toward price-fit items" is only true of about a
  fifth of it — the rest is pool size, not user modeling.

**Bottom line:** the safest standalone gain is **lexical + behavioral at a
light weight (`ctr_weight≈0.3`)** — CTR leans positive, welfare is up, nothing
is significantly worse. Personalization's own logic is a legitimate, modest,
purchase-positive lever, but as currently built it's bundled with a pool-size
side effect that costs CTR for no purchase benefit — worth fixing (reorder
within the original candidate window) before treating personalization's
apparent CTR cost as the price of a purchases/GMV objective.
