# IQ1_M prefill on the RTX 2080: final results

**Later November 1 update:** the [compact-layout follow-up](compact.md) supersedes the buffer-layout decision below. Compact buffers plus a 16-token minimum for CPU sharing are now selected in production, with small prefill gains and documented decode/short-prompt tradeoffs. This page retains the original measurements and rejected candidates.

**Completed November 1, 2026. Selected for production: IQ1_M INT8 fusion with the old buffer layout.** Same-day paired 121K prefill improved **850.6 → 866.2 tok/s (+1.8%)**, saving about 2.6 seconds per cold prompt. Both arms passed 20/20 scored coding attempts and 4/4 near-capacity checks. Decode remained approximately unchanged. This is a small additional gain on the already tuned profile.

[Compact measurements and checks](results.json) include every screened candidate, failures, native token/time counters, cache metrics and executable hashes. Raw prompts, replies, credentials and machine assets remain in ignored `runtime/iq1m-20261031/`.

## Enabled configuration

Strata 0.2.9 / engine 0.1.55, RTX 2080 8GB / SM75 / 165W, i5-9600K, 64GB RAM. Same Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS 125B weights and NVMe placement throughout. Context capacity stays **131,072**, with 32,768 resident INT8 KV tokens, routing prior 1.5, spec4, prefill chunk 4,096, existing VRAM loans and hot session restore.

Add to the existing profile:

```text
STRATA_PF_FUSED_IQ1_M=1
STRATA_PF_FUSED_LEGACY_LAYOUT=1
STRATA_PF_WMMA=0
```

The adapter from [PR #4642](https://github.com/Niko1221/Strata/pull/4642) covers the three IQ1_M/Q2_0 fallback layers (8, 13, 37) in these mixed weights. Forty-five layers already used fused native-IQ prefill. The new layout override keeps the previous ring/buffer allocation while enabling the additional kernel. Quantized weights are preserved, but INT8 activation/intermediate rounding changes outputs: this is not a bitwise-equivalent transformation.

## Throughput and correctness

Rates aggregate tokens divided by native time, rather than averaging request rates or comparing total task duration.

| Workload | Previous production | Selected configuration | Change |
|---|---:|---:|---:|
| 121,016-token cold prefill | 850.61 | 866.22 | +1.84% |
| 32K prefill | 881.31 | 889.17 | +0.89% |
| 16K prefill | 866.48 | 874.93 | +0.98% |
| 4K prefill | 657.85 | 658.55 | +0.11% |
| Short chat decode | 57.44 | 57.09 | −0.61% |
| Scored coding decode | 62.00 | 62.16 | +0.26% |

The final 121K sequence used fresh engines in production/candidate/candidate/production order: production 853.5 and 847.8 tok/s, candidate 867.3 and 865.1. All cold and warm retrieval answers passed. Warm calls each reused 121,009 tokens; first-token times were 1.113/1.086 seconds on production and 1.252/1.005 on the candidate. There is no established warm-latency win. The standard speed suite used three repeats per case, with no failures or skipped cases.

| Coding validation | Previous production | Selected configuration |
|---|---:|---:|
| Scored attempts (same 10 tasks, twice) | 20/20 | 20/20 |
| Native generated tokens | 60,902 | 55,150 |
| Aggregate prefill tok/s on agent requests | 334.37 | 357.28 |
| Expert-pool cache hits | 80.47% | 80.60% |
| Resident share of all routed experts | 75.69% | 75.86% |
| Continuation prefix tokens reused | 92.90% | 91.65% |
| Continuation requests with a cache hit | 100% | 100% |
| Near-capacity independent file checks | 4/4 | 4/4 |
| Largest near-capacity prompt | 121,831 | 122,359 |
| Near-capacity continuation prefix reuse | 99.756% | 99.814% |

Scored suites ran production/candidate/candidate/production, with thinking enabled at the API, pinned Pi 1.4.0, fresh sandboxed workspaces and independent verifiers. Ordinary tasks reached up to ~16K; separate sessions started with 117,214 tokens and exercised retrieval, file edits, tools and resumed conversations near capacity, with compaction disabled. Near-capacity controls were collected earlier in the same campaign, not interleaved with the final candidate. The candidate also passed three 122,451-token exact-edit screens across fixed/automatic chunk sizes.

Generated text and tool paths differ, so agent prefill/decode rates are workload observations, not isolated kernel comparisons. The candidate's shorter total task time partly reflects fewer output tokens. Twenty attempts repeat ten tasks; this is a limited quality sample.

## Alternatives retained but disabled

- **Compact INT8 buffer layout:** 881.2 tok/s in the initial fixed-chunk screen, but only 1/2 exact edits passed (two literal replacements missed). A later automatic-chunk run reached 888.3 and passed; that does not erase the failure. Initial screening also had some rendering overlap, so its speed is not the final paired claim.
- **FP16 grouped WMMA:** repaired the existing IQ tile that exceeded Turing's 64KiB shared-memory limit. A 64-row tile uses 51,200 bytes; an opt-in 512-thread variant reduced one IQ1_M microbenchmark from 0.4838 to 0.4169 ms. Full-model 121K prefill improved only 851.1 → 858.7 (+0.9%); 16K/32K were +0.1%/+0.2%. Near-capacity checks passed 4/4, but ordinary scored suites were skipped after the performance gate. Code is retained, feature disabled.
- **Automatic larger chunks / embedding reuse accounting:** no repeatable improvement over the selected fixed 4,096 chunk. Not enabled.

## Validation and attribution

The IQ1_M adapter passed numerical reference, opt-out and 4K/4.5K/8K routed-batch checks, existing IQ2_S/IQ2_XXS checks and CUDA memcheck. All 46 existing fused device functions retain identical SASS; one IQ1_M function is added. Both FP16 thread layouts passed all eight numerical cases, with finite outputs; 512-thread CUDA memcheck reported zero errors. HIP, Windows and other GPUs were **not tested**. This campaign does not update the upstream PR or request cross-platform review.

Native metrics count GPU-generated tokens and actual engine segments. API prefix-cache metrics count client requests. The existing loop-closure guard caused one internal continuation per arm across the scored suites; its injected text explains the small API/native output-count difference. All final usage counters reconcile after accounting for it. Expert-pool hit rates exclude direct PCIe routes; the separate all-routed resident share includes them in the denominator.

TensorFold's [tiled quantized prefill](https://github.com/ashhart/TensorFold/blob/cb2ebf0540f42604e2759b2ddef497861e928248/src/tensorfold/cuda/kernels/qmm_prefill.cu) and [expert-stage sizing](https://github.com/ashhart/TensorFold/blob/cb2ebf0540f42604e2759b2ddef497861e928248/src/tensorfold/cuda/experts_prefill.cu) inspired the investigation. No TensorFold code was copied. The FP16 repair extends Strata's existing Volta implementation; the INT8 adapter extends its fused prefill. The historical **590 → 886 tok/s** gain came from the earlier fused-prefill/batch/VRAM-loan bundle, not this adapter. These measurements do not promise a similar gain on other hardware or weights.

## Reproduction and rollback

The scripts here use prepared private fixtures, immutable expert-profile copies and the existing benchmark workspace's task fixtures. They are not a standalone downloadable benchmark. Each arm starts a fresh engine, checks quiet-host telemetry and protects baseline assets. Commands on this prepared workspace:

```sh
cmake --build build/iq1m-current --target strata prefill_fused_iq_test pf_wmma_parity -j2
STRATA_WMMA_BENCH=1 STRATA_PF_WMMA_NT=512 build/iq1m-current/pf_wmma_parity
STRATA_PF_WMMA_NT=512 compute-sanitizer --tool memcheck --error-exitcode 99 build/iq1m-current/pf_wmma_parity
runtime/venv/bin/python rtx2080/experiments/iq1m-current/analyze.py
runtime/venv/bin/python rtx2080/experiments/iq1m-current/export.py
```

`validate_legacy.py` preserves the completed validation sequence. Its frozen baseline hashes intentionally no longer match after promotion: restore the original snapshot or prepare a new baseline and run labels before a new campaign. Never run it against live production. `CURRENT.json` records the tested binary and source hashes. The original executable is retained privately as `runtime/bin/strata-before-iq1m-20261101`; the original source/profile is commit `9446299b586b8d42c355e5fb54d23c397fdd6e69`. To disable this optimization on the new binary, set `STRATA_PF_FUSED_IQ1_M=0`; restore the original binary/profile for exact baseline rollback.
