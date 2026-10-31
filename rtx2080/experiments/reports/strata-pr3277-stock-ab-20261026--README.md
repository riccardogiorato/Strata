> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Stock Strata versus PR #3277 — 2026-10-26

Compared clean upstream Strata 0.2.3 / engine 0.1.48 (`5c8dd322528cc84f68f461ad54a506b9da8fa8d4`) against the same source with only [PR #3277](https://github.com/Niko1221/Strata/pull/3277) at `4450012270c81f89bbf415cc77ab04adf731e5fb` applied. Both engines and the server came from a clean upstream source archive. No local scorer, cache or PR #3281 borrowing patches were included.

RTX 2080 8 GB at 165 W; i5-9600K, 64 GB RAM, Linux. Swift 1.5 Qwen3.8-Flash-Next GSQ-RCO IQ2_XS. Same 131,072-token capacity, `--prefill auto:131072 --expert-cache auto --spec 4 --spec-min-p 0.70 --kv int8 --kv-resident 32768 --pcie-frac 0.35 --vram-elastic`, native host conversation cache settings and expert-profile seed. Shared environment: `STRATA_KV_PREFETCH=1 STRATA_SM75_PERF=1`. Candidate additions: `STRATA_PF_FUSED=1 STRATA_PF_FUSED_SM75=1 STRATA_PF_FUSED_NATIVE_SM75=1`. Exact configurations are in `metadata.json`.

Four serial fresh-engine requests, stock / PR / PR / stock, using the same 122,451-token complete-file edit. Zero cached tokens, temperature 0, startup excluded; thinking disabled and archived responses checked. Each output is compared with the required full Python file using an exact AST check.

| Metric | Stock | Stock + PR #3277 |
|---|---:|---:|
| Prefill, aggregate tok/s | 591.20 | 600.47 |
| Decode, aggregate tok/s | 57.30 | 56.45 |
| Complete request, mean seconds | 232.301 | 229.496 |
| Individual wall seconds | 231.858 / 232.744 | 229.942 / 229.051 |
| Output tokens per request | [1433, 1433] | [1433, 1433] |

PR relative to stock: prefill +1.57%, decode -1.48%, full wall time -1.21%.

Correctness: 4/4 complete-file AST checks passed; candidate native format reference-check exit code 0. This is a focused high-context comparison, not a new full agent benchmark. No claims for other GPUs, models, HIP/SYCL, vision, long soak or statistical significance. A speed difference on this workload is not a universal agent speedup.

`stock-manifest.json`, `pr3277.patch`, `build-complete.json` and `metadata.json` identify source, executables and configuration. Raw SSE responses, engine logs and `results.jsonl` preserve each run. `runtime-plans.json` records selected prompt chunks. `final-state.json` verifies that production files, the GPU power limit and Bolt were restored. No production replacement was made.

The existing [PR comment](https://github.com/Niko1221/Strata/pull/3277#issuecomment-6416382243) was edited to report this baseline-to-PR comparison.
