# Yukon-inspired experiments on RTX 2080

**Result: retain these prototypes on the research branch; no production promotion.**
The isolated kernels showed gains, but the complete model did not show a reliable
prefill improvement, and decode changes were neutral or slower in the main coding
and usual chat suites. One penalized-prose case was faster; its tradeoff is reported below. All correctness checks described below passed.

Branch: `experiment/yukon-three-20261101`. The engine changes are in `0f3c0665`.
Production remains the protected configuration from `83ecef96`, with executable
SHA-256 `2698152f7ab0e08f1246d7d28b1d674f3a1746bc788e005538ff02d1347962e3`.
The tested experimental executable is
`263104ca29739f782b87ceb7800648deb1da22b4ffa1d97c84d13b7eb85fe067`.
[One compact evidence file](results.json) records counters, checks and log hashes.
Raw prompts, generated code, credentials and model files remain in ignored runtime storage.

## Complete-model measurements

RTX 2080 SM75, 8 GiB at 165 W; i5-9600K; 64 GiB RAM; NVMe weights.
Model: Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS, 125B MoE with mixed quantization.

All arms preserve 131,072 context capacity, 32,768 resident INT8 KV tokens,
MTP spec4/min-p 0.70, residency routing prior 1.5, PCIe expert access, adaptive
expert caching, prefill VRAM loans, the current fused prefill kernels and hot RAM
session restore. Each server gets an identical independent expert-profile copy.
No compiler or other GPU job overlaps the throughput runs.

Rates are tokens divided by native engine time. The usual suite uses three runs
per test with thinking off. The fixed edit has exactly 122,451 cold input tokens
and produces 1,433 output tokens in every arm; its resulting Python AST must
match the expected edit. Controls bracket the candidate sequence.

| Arm | Chat decode tok/s | 32K prefill tok/s | 122K prefill tok/s | 122K edit decode tok/s |
|---|---:|---:|---:|---:|
| Options-off control | 57.5 | 887.8 | 867.6–871.7 | 81.2 |
| Deferred recurrent state | 55.1 | 888.5 | 868.5 | 81.1 |
| Grouped alpha/beta projections | 57.9 | 889.9 | 870.1 | 80.9 |
| Fused greedy output head | 56.4 | 886.3 | 867.8 | 78.2 |
| Head layout only, without selection fusion | 56.7 | 887.3 | 867.9 | 81.3 |

All six usual speed suites passed without failures/skips; all six fixed 122K
edits passed. The installed production binary was also measured first: 57.7 tok/s
chat and 894.2 tok/s at 32K. That early run started cooler. The warmed options-off
build is the more relevant candidate control. The 32K ranges overlap, and the
candidate 122K prefill rates lie inside the bracketing controls' variation.
There is one fixed-edit run per candidate, so tiny differences are not evidence
of a repeatable improvement.

## Thinking-enabled agent and cache checks

One Pi coding scenario starts with 117,214 tokens, performs an exact source edit,
retrieves a value from the archive, and verifies both with tools. A resumed turn
changes the value again and adds a docstring. Compaction is off for this explicit
near-capacity test; normal production context fitting stays enabled. Requests
actually sent to Strata have thinking on, temperature 0 and seed 42.

| Arm | Initial + follow-up checks | Highest prompt | Generated tokens | Decode tok/s | Expert hit rate | Continuation token reuse |
|---|---:|---:|---:|---:|---:|---:|
| Options off | 2/2 | 121,894 | 2,497 | 63.23 | 80.37% | 99.81% |
| Deferred state | 2/2 | 127,990 | 8,392 | 57.75 | 80.37% | 99.85% |
| Grouped projections | 2/2 | 121,020 | 1,937 | 61.03 | 79.92% | 99.75% |
| Fused head | 2/2 | 122,298 | 3,245 | 59.96 | 79.77% | 99.77% |

Every continuation request hit the prefix cache in every arm. API timings and
counts reconcile with the native engine segments. All runs used tools and ended
cleanly. Scenario scores come from the explicit file/AST/value checks, not the
generic harness's `verify.sh` field: this scenario has no `verify.sh`.

This is one scenario and its follow-up per arm, **not the full ten-task coding
benchmark or a quality ranking**. The model generated different amounts and kinds
of reasoning. Grouping projections finished earlier with fewer output tokens,
although its decode rate was lower. Deferred state generated over three times as
many tokens. Neither task duration nor the observed agent-rate differences alone
is a causal measurement of a kernel change.

## Sampling comparison

A fixed prose request exercises greedy, temperature-0.7 sampling, sampling with
presence/frequency penalties of 0.2, then greedy again. Each response generates
768 tokens. These short-prompt policy probes complement the high-context tests;
they are not a quality score. Native counts and timings reconcile for all 24 calls.
Rates below are decode tok/s.

| Run | Greedy | Sampled (0.7) | Sampled + penalties | Greedy again |
|---|---:|---:|---:|---:|
| Control before | 55.97 | 53.61 | 54.67 | 56.34 |
| Fused head | 56.60 | 54.47 | 57.26 | 55.57 |
| Layout only | 58.01 | 54.18 | 55.06 | 54.53 |
| Control after | 58.49 | 53.69 | 54.11 | 57.14 |
| Fused head repeat | 56.34 | 49.64 | 55.56 | 57.31 |
| Control repeat | 58.14 | 54.32 | 54.37 | 58.52 |

The first penalized-prose result was positive, so it was repeated rather than
rejected: the fused head measured 57.26 versus controls 54.11–54.67 tok/s, then
55.56 versus 54.37 on the repeat. That is an observed narrow upside of roughly
2–5%, with changed text and speculative acceptance. It is not a clean isolated
measurement of fusion: the sampled path reconstructs full logits and does extra
head work. Greedy results were mixed and the main coding measurements regressed.
This tradeoff is retained in the evidence; it does not justify a global production
replacement for the coding workload. A sampler-specific graph design is not
implemented in this prototype.


## Profile and kernel findings

The corrected `baseline-profile-idle` run profiles roughly 32K and 122K, cold and
warm, with thinking on. Instrumented rates are diagnostics, not A/B speed results;
verifier profiling changes some execution paths. The first diagnostic pass is
excluded because it overlapped compilation, omitted a timing switch and used
thinking off.

Multi-window rounds took about 32–45 ms. The head was roughly 1 ms per window and
the asynchronous commit graph about 0.78 ms. Expert execution and waits dominate.
Overlapping stage times cannot simply be added to predict a speedup.

### 1. Cross-round recurrent-state fusion

The next verifier window folds the previous accepted prefix into its recurrent
state, using a small reused scratch buffer. A final flush materializes pending
state before request/session boundaries and resource loans. It supports the tested
single-slot, unsplit path; unsupported combinations are rejected.

The initial generic fusion was slower. A four-block-per-head variant passed all
72 bitwise state/output combinations through T8 and accepted prefixes 0–8, plus
the production T1 self-commit comparison and the boundary flush. The tests also
compare against the existing split reference. At T5/keep5, an earlier idle
microbenchmark measured 24.37 → 20.97 us against a separate per-layer commit and
verification, but only 22.05 → 20.95 us against the split reference. Gains were
not uniform at wider windows.

That microbenchmark overstates the production opportunity: Strata already batches
commits across layers, overlaps them with drafting, and self-commits T1 windows.
This deferred prototype disables the T1 self-commit shortcut and adds scratch-copy
work. The measured complete-model result does not justify deploying it. This is
a result for this implementation, not proof that every deferred-state design is slower.

### 2. Shared-input projection grouping

All 36 alpha/beta pairs in this pack are adjacent BF16 matrices. They can share
one GEMM, including the low-part accumulation, without duplicating weights or
allocating another persistent buffer. Incompatible layouts fall back to the
ordinary calls. The engine log confirms the grouped path actually ran.

Ten shape/low-part cases passed bitwise, including odd sizes and 4096 tokens.
At T4096 with the low part, separate GEMMs took 1346.19 us versus 1042.07 us grouped.
These are two small projections: their savings did not produce a measurable
complete-model prefill gain. The larger QKV/gate projections use different quant
formats; they are not grouped here. Decode already shares the quantized activation
across several projections.

### 3. Exact greedy output-head fusion

The prototype selects exact top-1 while computing the IQ4_XS output head. It keeps
the full 248,320-token vocabulary, lowest-ID tie behavior and nonfinite detection.
Partials reuse the existing logits allocation. Sampling, penalties and logprob
consumers materialize full logits on demand; that fallback adds work.

Full-size 2560 × 248320 tests passed bitwise logit comparisons, token selection,
ties and nonfinite checks. Generic fusion was slower. Interleaved fusion regressed
T2–4, so the engine experiment uses only T1/T5. At T5, the original head took
3067.92 us, interleaved fusion 1518.46 us, and **layout-only 1382.50 us**: most of
the gain was layout coverage, not selection fusion. At T1 fusion was 847.18 us
versus 905.31 us layout-only.

Under the current spec4 profile, ordinary decode windows are at most four tokens;
wider prompt-admission windows also occur. The large T5 kernel result is not
representative of steady decode. The complete-model measurements do not support
promoting either head variant.

## Provenance and reproduction

Inspiration: TensorFold/Yukon's [shared-input projection change](https://github.com/Layr-Labs/cudafast-qwen38-27b-tf-engine/commit/a7e1df5ee7be)
and [deferred recurrence / greedy head change](https://github.com/Layr-Labs/cudafast-qwen38-27b-tf-engine/commit/0d741603b4b8).
These are locally implemented adaptations of concepts from a different GPU and
weight format; their GB10/affine-4 kernels are not a drop-in replacement for SM75/GGUF.

Only CUDA SM75 has been built/tested. HIP, SYCL and Metal are untested; no upstream
PR was opened. All five arms passed API checks for greedy replies, sampled
logprobs, penalties, returning to greedy, and a forced tool call (25/25 checks).

Build targets: `strata`, `yukon_gdn`, `yukon_projections`, `yukon_head` in the
isolated `build/yukon-three` CUDA build. Run the recurrence test with
`STRATA_YUKON_COMMIT_SPLIT=1`, and repeat with `STRATA_GDN_SPLIT=1` for the split
reference. Run the head test with the production `STRATA_SM75_PERF=1` switch.
Kernel tests use generated data. Model-level scripts use local private fixtures
and the protected production profile; those private fixtures are not published.

`run.py` runs one isolated arm, `sweep.py` runs arms sequentially, `summarize.py`
reconciles private evidence, and `publish.py` writes the compact public counters.
Experimental flags, all off by default:

- `STRATA_YUKON_COMMIT=1` and `STRATA_YUKON_COMMIT_SPLIT=1`
- `STRATA_YUKON_PROJECTIONS=1`
- `STRATA_YUKON_HEAD=1`
- Separate control: `STRATA_YUKON_HEAD_LAYOUT=1`

The production binary/profile are protected by hashes before and after every run.
These experiments remain in the same canonical repository, on a separate branch;
no extra sibling checkout or production engine replacement is needed.
