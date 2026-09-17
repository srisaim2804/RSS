# Report For Search Components

## Round-by-round results

| Round | Ranker | Expected value | Sampled value | Δ vs. BM25 baseline | Δ vs. semantic baseline |
|---|---|---|---|---|---|
| 1 (valid, but worse) | RRF + personalization | 0.06626 | 0.06527 | −0.0046 | −0.0131 |
| **1** | pure RRF (BM25 + semantic + quality) | **0.07225** | 0.07142 | +0.0014 | −0.0081 |
| **2** | + behavioral CTR (round 1 data) | not recoverable\* | 0.07225\*\* | ~flat | — |
| **3** | + behavioral CTR (rounds 1+2 data) | **0.07443** | **0.07449** | **+0.0037** | −0.0048 |

*\*A real server bug (`/report` hangs indefinitely — reproduced 3 times, see
the tester feedback note) meant round 2's closed-form expected value isn't
recoverable. \*\*Round 2's sampled value is not a guess: it's the exact
server reward formula, reverse-engineered from round 1's two known
`(action_counts, sampled_value)` pairs — `sampled_value_per_impression =
(1.0·purchase + 0.3·cart + 0.1·click) / n_impressions` — and verified against
both round 1 runs to 8+ significant figures before being applied to round
2's real, server-confirmed action log.*

**Bootstrapped significance** (2,000 resamples on the real per-impression
reward, using the formula above, applied consistently across all three
rounds so the comparison is apples-to-apples):

| Comparison | Δ | 95% CI | Significant? |
|---|---|---|---|
| Round 1 → Round 2 | +0.00083 | [−0.00029, +0.00193] | No |
| Round 2 → Round 3 | +0.00224 | [+0.00116, +0.00340] | **Yes** |
| Round 1 → Round 3 | +0.00307 | [+0.00197, +0.00419] | **Yes** |

## Action-level detail, all three real rounds

Every number below is from the real per-round action log (288,000 served
impressions each). `reach_rate` is the server's own definition — verified:
locally-recomputed reach rates for round 3 matched the server's reported
values to 4+ decimal places before being trusted for rounds 1 and 2, where
`/report` wasn't available (see the CI note above).

| Action | R1 count | R2 count | R3 count | R1 unique items | R2 unique items | R3 unique items | R1 reach | R2 reach | R3 reach |
|---|---|---|---|---|---|---|---|---|---|
| seen | 232,092 | 231,996 | 230,799 | 3,024 | 2,896 | 2,984 | 97.45% | 97.12% | 97.20% |
| click | 23,251 | 23,134 | 23,351 | 2,437 | 2,326 | 2,420 | 78.54% | 78.00% | 78.83% |
| cart | 20,591 | 20,537 | 21,045 | 2,382 | 2,279 | 2,392 | 76.76% | 76.43% | 77.92% |
| purchase | **12,066** | **12,333** | **12,805** | 2,094 | 1,977 | 2,071 | 67.48% | 66.30% | 67.46% |

**Catalogue coverage** (distinct items the ranker actually put in a slate,
out of 100,000): R1 2,412 (2.41%) → R2 2,304 (2.30%) → R3 2,403 (2.40%) —
essentially flat across rounds; the behavioral channel is re-weighting
*which* items in an already-narrow candidate set get shown, not widening or
narrowing that set.

**Traffic composition** (head/middle/tail bucket sizes, user-segment pair
counts) is a property of each round's traffic file, not of the ranker, and
was materially stable across all three rounds — head ~49.4%, middle
~27.9%, tail ~22.7% of pairs in every round; per-round `/report` bundles
this in but withholds per-bucket and per-segment scores ("omitted to avoid
answer extraction"), so it isn't something a ranker choice can be tuned
against.

## How the ranker got here

**Round 1 started with a bug that cost real score, not a rounding error.**
The first valid submission blended a per-query Reciprocal Rank Fusion base
(BM25 rank + semantic rank + quality rank, `k=60` — adapted from a
teammate's approach, which independently validated at 5-12 minutes of
real server-side simulation time and clued in that this session's earlier
multi-hour submission times were an infrastructure problem, not a workload
one) with a raw additive per-user personalization nudge (`price_sensitivity`
→ prefer cheaper, `review_dependency` → prefer higher-rated — the only two
of the bundle's 8 numeric user features with an unambiguous sign from the
name alone). That combination scored **0.06626** — *below* both the BM25
(0.0709) and semantic (0.0793) baselines.

Diagnosis: RRF's rank gaps near the slate cutoff are tiny (`1/61 − 1/62 ≈
0.00026`), so even a deliberately "small" additive weight (0.02) ends up
dominating instead of nudging — it changed the **#1 item for 58% of pairs**.
Removing it and resubmitting pure RRF in a fresh session scored **0.07225**
— a +0.006 absolute swing from one component that was supposed to be
minor. **Personalization's default weight is now 0.0** everywhere in this
codebase; the mechanism is still there, documented as unvalidated, not
deleted.

**Round 2 applied the lesson properly, not just removed the bug.** Instead
of re-adding behavioral CTR (learned from round 1's real, propensity-IPS-
weighted action log) as another raw additive nudge, it was folded into the
*same* RRF rank-fusion mechanism as the quality channel — a 4th ranked
channel, not a raw score. Locally, this changed the #1 item for only 26% of
pairs (vs. 54% for the naive additive version tested but not shipped) — a
properly-scaled nudge. Result: +0.00083 sampled-value delta over round 1,
**not statistically significant on its own** — round 2 alone is not
strong evidence the behavioral channel works.

**Round 3, with two rounds of real behavioral data instead of one, is where
it becomes real.** Same rank-fused approach, same personalization left off,
just more signal. **+0.00224 over round 2, CI excludes 0.** Cumulatively,
round 1 → round 3 is also significant (+0.00307, CI [+0.00197, +0.00419]).
Purchases climbed every round: 12,066 → 12,333 → **12,805** — the
deepest, highest-weighted action in the server's own reward formula.

## What this shows

**The ranker's real gain is small in absolute terms (+0.003 expected value,
~4% relative over round 1) but it is statistically real, not noise, and it
came from disciplined process, not from picking a fancier algorithm.**

- **A raw additive score and an RRF rank-fusion score are not
  interchangeable**, even when the raw weight is deliberately tuned "small."
  This cost the very first valid submission a measurable amount of real
  score, discovered only because the result underperformed a plain baseline
  it should have beaten. The fix generalizes: any future signal added to
  this ranker should be fused at the rank level, not the score level, unless
  there's a specific reason the scales are actually comparable.
- **Behavioral learning needs more than one round of data to show up as
  signal, not luck.** Round 2 (one round of behavioral history) moved the
  score but the interval crossed 0 — a plausible false lead. Round 3 (two
  rounds of history, same mechanism) is the one with a CI that excludes
  0. Reporting round 2 alone as "it works" would have been premature.
- **The infrastructure cost more real time than the ranker design did.**
  Getting from "have the assignment PDF" to "one valid graded round" took
  most of this session — wrong-architecture image, missing Docker/WSL2,
  three multi-hour emulated attempts (one ran ~17-18 hours before dying),
  before a teammate's own measured numbers (5-12 minutes, server-side) made
  clear the problem was never the workload. Once running on the correct
  architecture, all three graded rounds together took under two hours.
- **The simulator itself has a real, reproducible bug** (`GET .../report`
  hangs indefinitely and then blocks that endpoint for *other* sessions too,
  while `/health` and every other endpoint stay responsive) — worked around
  by relying on the submission response, which turns out to already carry
  everything `/report` would have (confirmed directly: round 3's submission
  response came back with the full baselines/actions/coverage payload, no
  separate call needed). Full reproduction steps and two more defects are in
  `tester/FEEDBACK.md`.

**Bottom line:** pure RRF (BM25 + semantic + quality) is the safe floor —
it's the only round-1 configuration that beat any baseline at all. Behavioral
CTR, fused at the rank level and given two rounds to accumulate real signal,
is a legitimate and *significant* improvement on top of it (+0.0037 vs. the
BM25 baseline by round 3, up from +0.0014 in round 1). Naive per-user
personalization, as first implemented, was not a legitimate improvement — it
was a measured regression from a raw-score scaling mistake, and it stays
off by default until it's re-validated properly (most likely: also folded
into the rank-fusion mechanism, the same way behavioral CTR was, rather than
re-tried as a raw nudge at a smaller weight).
