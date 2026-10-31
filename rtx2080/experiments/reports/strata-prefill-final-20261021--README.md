> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Final prefill screen and VRAM borrowing validation — 2026-10-21

Recommendation: use the PR #3281 borrowing-only build for faster long prefill. Keep PA_V2T and BF16_TC unset. No new configuration was deployed; the original authenticated production service was restored. `recommended-config.json` is a prepared configuration only, and relies on the existing managed service authentication setup.

## Latest matched production versus borrowing-only comparison

| Measurement | Production | Borrowing only |
|---|---:|---:|
| 20,063-token real coding history: full request | 29.72 s | 24.82 s |
| 20,063-token real coding history: prefill | 693.8 tok/s | 830.0 tok/s |
| 121,787-token real coding history: full request | 178.18 s | 146.75 s |
| 121,787-token real coding history: prefill | 689.1 tok/s | 838.8 tok/s |
| Sustained decode (two 2,048-token outputs) | 55.80 tok/s | 55.99 tok/s |
| Cached follow-up (256 output tokens, one request) | 6.45 s | 7.34 s |
| Three Pi tasks: full task time | 138 s | 149 s |
| Pi correctness | 3/3 | 3/3 |
| Retrieval at ~20K and ~121K | 2/2 | 2/2 |

The cached follow-up was slower with borrowing in this single pair. This is evidence to retain, not a reliable regression estimate: the generated histories and MTP acceptance differ. The recommendation concerns cold long prefill, not a claim that every agent turn gets faster.

## Screen

Four fresh boots: production, PA_V2T=1, BF16_TC=1, production. All four passed the ~20K retrieval check. Relative to the mean of the bracketed production runs, PA_V2T increased the 20K full request time by 1.76% and BF16_TC by 0.83%. Neither cleared the predeclared 3% improvement threshold; neither was combined with borrowing or tested at 122K in this fast screen.

Prior BF16 evidence: ../../measurements/strata-0140-bf16tc-2026-10-06.txt also showed no reliable prefill benefit on the older engine. BF16_TC uses FP16 tensor-core projections on Turing; PA_V2T and BF16_TC can change numerical results.

## Method and limits

Same Q2_0 GSQ-RCO model paths, 131072 maximum context, 32768 resident KV, int8 KV, spec=4, 165 W, deterministic request parameters. Same request bodies across arms, cold cache asserted. Boot-per-arm, 30-second idle interval, 512-token warmup, serial GPU workloads. Final order: borrowing then production, reversing the earlier comparison. Full HTTP time includes restoration overhead, but short generated responses can differ in length; output counts are saved. Fixed-length decode totals 4096 output tokens per arm.

Pi tasks: JavaScript repair, JavaScript-to-TypeScript conversion, long-context gateway repair. Existing benchmark wrapper with bwrap: private home/tmp, only the current task writable, old benchmark answers hidden, private writable Pi config. Protected files and agent errors audited. Single run per task/arm: task time differences do not establish a general coding speedup or regression.

Six boots total. Flags only received a short screen; this does not exclude benefits at other lengths or with other formats. No new PCIe retention test, no expert-cap test, no broad flag sweep, no full eleven-task suite, and no extended stability soak. Earlier larger validation is in ../strata-combined-agbench-20261021-r1/README.md. The earlier standalone borrowing ABBA evidence is in ../strata-optimization-ab-20261021/README.md.

## Reproduce and audit

`run.py screen` and `run.py validate` preserve existing results and restore the service in finally. Use a new output directory for a new experiment. `validation-plan.json` records the selected build and flags; `binary-manifest.json` pins binary hashes. `results.jsonl`, configs, responses, engine logs and `coding/` retain raw evidence. `summary.json` contains derived comparisons; `final-validation.json` records context, power, correctness and restoration checks.

Upstream feature: https://github.com/Niko1221/Strata/pull/3281. This is the pinned custom borrowing build, not a claim that the PR is merged.
