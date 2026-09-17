# Tester feedback — ire-a2-tester-api

Full 3-round session completed against the real simulator (native amd64,
after working through several infrastructure problems — see §1). This is
the complete feedback note requested by the assignment brief.

## 1. Setup problems

- No defect in the image itself, but worth recording for anyone repeating
  this: this host had neither Docker Desktop nor WSL2 installed. Full path
  to a working container: install Docker Desktop → `wsl --install` (needs
  admin elevation) → reboot → Docker Engine up. Budget real time for this on
  a from-scratch host.
- The provisioning/distribution side is the real issue: only an **arm64**
  tar was locatable on the host at first; this machine is amd64/x86_64. The
  correct tar existed in the shared SharePoint/OneDrive folder the whole
  time, but its **hyperlink was only in the PDF's link annotation, not in
  the visible text** — copy-pasting or reading the PDF's text layer doesn't
  surface it; you have to actually click the link or extract link
  annotations programmatically. Recommend also stating the raw URL as
  visible text in the PDF, not just as a link behind "Click to open OneDrive
  folder."
- Running the wrong-architecture (arm64) tar under Docker Desktop's QEMU
  emulation on this amd64 host is *not* just proportionally slower — it's
  worth flagging as a trap, not just an inconvenience:
  - World build: ~13x slower under emulation (521-546s vs. the spec'd
    27-39s) — survivable.
  - **Submission scoring: ~80-200x+ slower**, not proportional to the
    world-build penalty. One attempt (8GB memory cap) was OOM-killed after
    ~1h50m. A second attempt (14GB cap) ran **~17-18 hours** before dying.
    A third (20GB cap, WSL2 raised to 24GB) was still running, memory
    climbing calmly with no OOM, when abandoned in favor of the correct
    tar. The scoring endpoint appears to fan out heavily (observed PIDs
    climbing past 700 during one run) — QEMU's binary translation is
    disproportionately bad at heavy multiprocessing specifically, not just
    raw CPU-bound work, which is why world-build and scoring hit completely
    different penalties under the same emulation.
  - On the correct architecture, world build took **24.0 seconds** (even
    faster than the spec'd estimate) and round submissions consistently
    took 5-31 minutes end-to-end. Architecture match matters enormously more
    than any other factor tested this session.

## 2. Runtime and memory use

- **World build time (native, correct arch)**: 24.0s. Matches spec.
- **Peak RSS at idle**: 3.46-3.57 GiB across every run, arch-independent —
  matches the spec's stated "3.5-4 GiB RAM."
- **Round submission timing (native, correct arch)**, all three graded
  rounds actually run:

  | Round | Server-side sim time | Total (incl. our HTTP round-trip) |
  |---|---|---|
  | 1 (rejected, invalid) | 0.48s (fast-fail on validation) | ~13.3 min |
  | 1 (valid) | 421.4s | ~25.9 min |
  | 2 | not measured (see the `/report` bug below) | >30 min (client timeout), succeeded server-side |
  | 3 | 660.2s | ~31.3 min |

  The gap between server-side sim time and total time (several minutes) is
  consistent but unexplained by anything in the docs — worth documenting
  what else the round-trip includes (upload of a ~95-480 KB file shouldn't
  account for it on localhost).
- **`/v1/bundle`**: logged as `200 OK` in the uvicorn access log well before
  any response bytes reached the client (confirmed via `docker stats`: CPU
  pegged, network I/O flat, for several minutes after the 200 was logged,
  then the full ~372 MB arrived at once). Likely an artifact of how the
  access-log middleware times a streaming response, but it makes the access
  log a misleading progress signal for anyone scripting against this
  endpoint.

## 3. Unclear schema or contract text

- **Embedder mismatch (major, reproducible)**: `schemas.json` →
  `embedder.provider` is `"sentence_transformers"` (the real catalogue
  embeddings are MiniLM vectors). But the bundle's own `student/example.py`
  — the file whose docstring says it "touches ONLY the bundle tree" and is
  the quick-start entry point — hardcodes `MockHashEmbedder` regardless of
  what `schemas.json` declares. A student who runs the shipped example and
  extends it verbatim will silently compute query vectors in the *wrong*
  space relative to `catalogue.embedding`. (`make_embedder()` in the same
  file *does* dispatch on `provider` correctly — the bug is specifically
  that `example.py` doesn't call it.)
  - Repro: `PYTHONPATH=student python student/example.py`, then compare
    `schemas["embedder"]["provider"]` (`sentence_transformers`) against the
    embedder class actually instantiated in that same file
    (`MockHashEmbedder`).
  - Mitigating factor: for the 144 *published* queries,
    `query_embeddings.parquet` already ships the correct precomputed
    vectors, so a ranker that joins on `query_id` instead of re-embedding
    `query_text` never hits this bug. It only bites someone who tries to
    embed novel query text themselves.
- **No documented semantics for the 8 numeric user features**
  (`price_sensitivity`, `brand_loyalty`, `review_dependency`,
  `ad_susceptibility`, `domain_knowledge`, `novelty_preference`,
  `variety_seeking`, `deal_seeking`). Values look standardized (~N(0,1),
  signed) but nothing in `schemas.json`, `/v1/spec`, or the student bundle
  states which direction is "more" of the trait. This has a real, measured
  cost: guessing the sign/weight for two of these features (even the two
  with unambiguous names) and applying them as a raw additive ranking nudge
  cost 0.006 absolute expected-value in round 1 (see `README.md`) before
  being diagnosed and removed. A worked example or a stated sign convention
  in the docs would have prevented this.
- **`/openapi.json` response schemas are all bare `{}`** for every endpoint
  — FastAPI/Starlette declares no response model, so `/docs` gives no
  field-level documentation anywhere. Every response shape in this note was
  discovered empirically.
- **The scoring/reward function is undocumented but reverse-engineerable.**
  Neither the assignment brief nor any bundle file states how
  `sampled_value_per_impression` is computed from action labels. From two
  known `(action_counts, sampled_value)` pairs in round 1, the exact formula
  turned out to be `(1.0·purchase + 0.3·cart + 0.1·click + 0.0·seen) /
  n_impressions` — verified to 8+ significant figures. Worth stating this
  explicitly in the docs (or in `/v1/spec`), since it's directly useful for
  anyone trying to optimize toward the metric rather than a proxy.
- **Baselines are not constant per-world**, contrary to what the /v1/spec
  wording implies. The BM25 baseline read 0.070867 in round 1's report and
  0.069697 in round 3's — a ~0.0002 drift, small but real, presumably from
  slightly different per-round traffic sampling. Not a bug, but worth
  stating explicitly rather than leaving testers to assume baselines are
  world-level constants (this report initially did, and had to correct
  itself).

## 4. Validation quality

Validation is fast, accurate, and its error text is genuinely actionable —
the one real defect encountered was fully explained by the error message:

- Our own bug (dedup'd traffic incorrectly, producing 40-row slates for 184
  repeated-impression pairs) got a clean, specific **422** naming the exact
  pair and the exact malformed rank list:
  `"pair (Q00038, U000375): the ranks must be 0 to 39 with no gap and no
  repeat, got [0, 0, 1, 1, ..., 19, 19]"`. That was enough to diagnose and
  fix the bug without needing to inspect our own submission file further.
- No false accept was observed: our own local validator (checking rank
  *sets* rather than exact row counts) missed the same bug that the
  server's 422 caught — the server's validation is stricter and correct
  where ours briefly wasn't.
- One nuance worth documenting explicitly: validation and simulation appear
  to be one combined server-side pass, not two — a 422 for a large
  submission can still take real time to return (in our case, a few hundred
  ms to fail on a fast structural check, but nothing guarantees that for
  every validation failure mode).

## 5. Ranker development experience

- The `student/` bundle is a genuine strength: no dependency on the course
  repos, vendored BM25 (`bm25.py`) and embedder (`embedder.py`) with
  matching math, and `load.py` helpers cover every file in the bundle.
  Round-tripped the vendored `Bm25Index.from_pickle` against
  `catalogue_bm25.pkl` with no changes needed.
- `forbidden_bundle_names` / `forbidden_column_substrings` in
  `schemas.json` are a nice, explicit guardrail — clear about what's
  off-limits (oracle scores, latents, hidden relevance) without having to
  guess.
- Cost of iterating is real even at native speed: 5-31 minutes per round
  submission is a hard ceiling on how much can be tested inside one
  session. This favors iterating one ranker round-over-round (using each
  round's own action log to improve the next) over comparing many
  ranker variants side-by-side, each needing its own full round — the
  `16 sessions per container` budget is generous, but wall-clock time is
  the binding constraint, not session count.

## 6. Bugs — summary table

| # | Component | Expected | Actual | Severity | Repro |
|---|---|---|---|---|---|
| 1 | `GET .../rounds/{r}/report` | Returns the round report | **Hangs indefinitely** (tested with 30s, 60s, and 120s client timeouts, all hung) for a session, and while hung, **blocks `/report` for other sessions too** — while `/health` and every other endpoint stay fully responsive. Reproduced 3 separate times across this session. | **Major** | Submit a valid round, then `GET /v1/sessions/{sid}/rounds/{r}/report`. Workaround found: the submission POST response already carries the complete payload (score, baselines, deltas, actions, coverage, traffic buckets, segments) — confirmed identical in shape to what `/report` would have returned. A client that saves the submission response directly never needs `/report` at all. |
| 2 | `student/example.py` | Uses the embedder matching `schemas.json.embedder.provider` | Hardcodes `MockHashEmbedder` regardless of the declared provider | Major | `PYTHONPATH=student python student/example.py`; compare against `schemas.json` |
| 3 | `/openapi.json` | Typed response schemas for at least the JSON-returning endpoints | Every endpoint's response schema is `{}` | Minor | View `/docs` or `/openapi.json` directly |
| 4 | `/v1/bundle` access log | `200 OK` logged when the response is actually ready to read | `200 OK` logged minutes before any response bytes are sent | Minor | Watch `docker logs` timing vs. `docker stats` network I/O during a bundle download |
| 5 | Documentation | Baselines described as world-level | Baselines drift slightly per round (~0.0002 on BM25 baseline between round 1 and round 3) | Minor | Compare `baselines` across two rounds' reports in the same session |

## 7. What would have most helped a tester

In order of impact: (1) ship the amd64 *and* arm64 tars together, or at
minimum make the download link's URL visible as plain text, not only as a
PDF hyperlink annotation — the architecture mismatch alone cost most of a
day; (2) fix the `/report` hang, or document the submission-response
workaround directly in the brief; (3) state the reward formula and the
numeric user-feature sign conventions explicitly, since both are
reverse-engineerable but shouldn't need to be.
