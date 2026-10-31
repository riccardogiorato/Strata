> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Local fusion versus upstream PR #3277 — 2026-10-26

Prefill was within 1% at every tested length. Our patch finished the repeated 122K complete-file task about 1% sooner. Short-chat decode tied; our patch was about 3% ahead in the long-file and conversation decode samples. This comparison does not establish a performance reason to replace our installed patch with #3277.

Head-to-head comparison of our local Turing native-IQ fusion patch and the complete diff from [Strata PR #3277](https://github.com/Niko1221/Strata/pull/3277). Both engines were freshly built from the same frozen modified Strata 0.2.3 / engine 0.1.48 source. The PR was applied to this common baseline; this is not a standalone build of its older base revision.

Pinned PR head: `4450012270c81f89bbf415cc77ab04adf731e5fb`. Common upstream base: `5c8dd322528cc84f68f461ad54a506b9da8fa8d4`, plus the pre-existing local loan, scorer and session patches recorded in `local-source.patch` and `source-manifest.json`.

## Matched setup

RTX 2080 8 GB, i5-9600K, 64 GB RAM, Linux, 165 W. Swift 1.5 Qwen3.8-Flash-Next GSQ-RCO IQ2_XS; context capacity 131,072; 32,768 resident int8 KV cells; prefill 4,096; expert cache 2,000; MTP 4; PCIe fraction 0.35. All inference settings were held fixed except the implementation-specific opt-in (`STRATA_PF_FUSED_SM75_IQ=1` for ours; `STRATA_PF_FUSED_NATIVE_SM75=1` for the PR). Both retain `STRATA_PF_FUSED=1` and `STRATA_PF_FUSED_SM75=1`, plus the same prefill loans. Every boot receives a fresh copy of the same expert-profile seed. CPU vision was configured, not exercised.

## Cold 122K complete-file edit

Four fresh engines, in ours / PR / PR / ours order. Identical 122,451-token request, no reused prefix, temperature 0; startup excluded. The task returns a complete Python file with the required integer replacement. Correctness is an exact AST comparison. Reasoning is disabled for these requests and checked in the recorded responses.

| Metric | Our patch | PR #3277 |
|---|---:|---:|
| Prefill, aggregate tok/s | 896.79 | 892.11 |
| Decode, aggregate tok/s | 58.83 | 56.88 |
| Complete request, mean seconds | 161.087 | 162.625 |
| Individual wall seconds | 160.099 / 162.074 | 162.359 / 162.890 |
| Output tokens per request | [1433, 1433] | [1433, 1433] |

Relative to our patch, PR #3277 changed prefill throughput by -0.52%, decode throughput by -3.30%, and complete-request wall time by +0.95%.

Complete-file correctness: 4/4 passed. Kernel reference-check exit codes: ours=0, pr3277=0.

## Usual speed suite

`tools/strata_bench.py --runs 3 --long`, once per arm, PR first then ours. This includes short chat, 4K/16K/32K prompts and synthetic six-turn conversations. It is not the full AG-Bench coding-task suite. These requests disable thinking.

| Median metric | Our patch | PR #3277 |
|---|---:|---:|
| Chat decode tok/s | 46.100 | 46.100 |
| Chat TTFT seconds | 0.924 | 0.883 |
| Conversation decode tok/s | 41.900 | 40.600 |
| Conversation TTFT seconds | 5.213 | 5.192 |
| 4K prefill tok/s | 654.10 | 659.40 |
| 16K prefill tok/s | 912.90 | 912.70 |
| 32K prefill tok/s | 921.80 | 927.00 |

Suite failures: ours=[], PR=[]. Skips: ours={}, PR={}.

## Limits and reproducibility

Two long requests per arm and three repetitions per suite probe are a focused local comparison, not confidence intervals or proof of a universal speedup. Full agent-task quality, vision, other models/quantizations, multi-GPU, HIP, SYCL and long stability soak were not rerun. Native reference checks use numerical tolerances; they do not establish bitwise equivalence to the unfused MMQ path. No new default or production binary was installed by this comparison.

`metadata.json` records exact settings and executable hashes. `build.log`, `pr3277.patch`, the source manifest, raw SSE responses, native engine logs, parity logs and speed-suite results preserve the evidence. The initial CPU-only CMake configure attempt omitted the CUDA option and had no `strata` target; it is retained in `build-initial-config-failed.log`. The corrected builds enable CUDA explicitly. `protected-check.json` verifies the production executable, configuration and expert-profile file were preserved; `original-state.json`, `restore.json` and `final-state.json` record service/power restoration.

## PR #3281 comment update

Edited the [existing October 21 comment](https://github.com/Niko1221/Strata/pull/3281#issuecomment-6316861059), keeping the original isolated borrowing results and the October 26 combined-configuration comparison. At the user’s request, the full comment was condensed from 894 to 90 words, combining the dated sections into one short summary. The newer combined-configuration gain is explicitly not attributed to borrowing alone; it predates this direct #3277 comparison. Before/after comment copies are retained. A [98-word result comment](https://github.com/Niko1221/Strata/pull/3277#issuecomment-6416382243) was subsequently posted to #3277 at the user’s request; its exact text and verified API response are retained.

Public-comment follow-up: the comment was subsequently replaced with a clean stock-versus-PR comparison (`../strata-pr3277-stock-ab-20261026/README.md`), as requested by the user. The measurements above remain the separate local-patch comparison.
