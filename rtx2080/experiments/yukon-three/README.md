# Yukon-inspired experiments on RTX 2080

Work in progress on `experiment/yukon-three-20261101`. Production stays at
`83ecef965dde2900e75f8272b409359118df8629`, binary SHA-256
`2698152f7ab0e08f1246d7d28b1d674f3a1746bc788e005538ff02d1347962e3`.
The production profile and executable are protected by hashes in ignored runtime evidence.

## Questions

1. Can folding the previous accepted recurrent prefix into the next verification
   kernel save time while preserving state and output bits?
2. Can adjacent BF16 alpha/beta projections share a prefill GEMM without extra
   allocation, and does this improve actual long-context coding?
3. Can an IQ4_XS output head select the exact greedy token while avoiding full
   vocabulary-logit traffic, retaining tie behavior and the nonfinite guard?

Inspiration: the promoted [TensorFold shared-input projection change](https://github.com/Layr-Labs/cudafast-qwen38-27b-tf-engine/commit/a7e1df5ee7be)
and [deferred recurrence / greedy head change](https://github.com/Layr-Labs/cudafast-qwen38-27b-tf-engine/commit/0d741603b4b8).
These are adapted concepts; their GB10/affine-4 kernels are not copied into SM75/GGUF paths.

## Method

- Keep 131,072 context capacity, resident KV 32,768, routing prior 1.5, MTP spec4,
  current mixed Swift IQ2_XS weights, VRAM loans and session cache fixed.
- Profile at roughly 32K and 122K with cold and warm requests. Instrumentation
  rates are diagnostics, not final speed results; verifier profiling can disable
  some fused paths. Do not compile or run other GPU jobs during final measurements.
- Test isolated kernels first: exact state/logit comparisons, all accepted-prefix
  lengths, vocabulary ties and nonfinite detection. Time captured CUDA graphs where
  production uses them. Kernel gains are not whole-model gains.
- Compare candidates separately against the same built source with options off,
  and verify that the off build remains comparable to the installed baseline.
- For viable candidates, run the normal speed suite, near-capacity edit/restore
  checks and thinking-enabled scored agent tasks. Report token-weighted prefill
  and decode, actual output counts, prefix reuse, expert hit rate and correctness.
- Record small gains and tradeoffs, including failed candidates. No automatic promotion.

## Evidence

Raw requests, model-specific fixtures, logs and build outputs remain under ignored
`runtime/yukon-three-20261101/` and `build/yukon-three/`.
The first diagnostic pass is explicitly excluded from A/B performance claims:
it omitted the decode-report switch and overlapped compilation for part of the
near-capacity run. The corrected idle pass is `baseline-profile-idle` (thinking on, no compiler overlap).

The initial unsplit recurrent prototype passed all 30 state/output bitwise checks,
but its first timing sweep was slower than separate commit + verification. A split
prototype is being tested before drawing a conclusion about the idea.

## Profile and isolated validation

The corrected profile measured 916.2 tok/s at 32K and 875.5 tok/s at 122K.
Those instrumented rates are diagnostics, not the A/B benchmark. A decode round
was roughly 34–41 ms, with about 1 ms in the output head and 0.78 ms in the
asynchronous commit graph. Expert execution and waits dominate. Overlapping GPU
stages cannot simply be added to predict a speedup.

- **Recurrence:** the generic fused version was slower. Splitting the work across
  four blocks per head passed all 30 bitwise state/output combinations (T1–5,
  accepted prefix 0–5), including the scratch copy and final pending-state flush.
  At T5/keep5 it measured 20.97 us against 24.37 us for the ordinary per-layer
  reference. Against the existing split reference it was only 22.05 → 20.95 us.
  Production batches commits across layers, so these microbenchmarks can
  overstate the whole-model opportunity.
- **Projections:** adjacent BF16 alpha/beta weights share one GEMM. Ten shape/
  low-part cases passed bitwise, including 4096 tokens. At T4096 with the low part,
  separate GEMMs took 1346.19 us versus 1042.07 us grouped. This covers only two
  small projections; the large quantized QKV/gate matrices are unchanged.
- **Head:** full-size 2560 × 248320 tests preserve every logit bit, top-1, lowest-ID
  ties and nonfinite detection. Generic fusion was slower. Interleaved fusion
  helps T1/T5 but regresses T2–4, so the engine experiment uses only T1/T5.
  At T5 the reference took 3067.92 us, fused interleaved 1518.46 us, and the
  **layout-only control 1382.50 us**. Most of that gain is layout coverage,
  not removing logits. At T1 fusion was 847.18 us versus 905.31 us layout-only.
  Sampling, penalties and logprob consumers materialize full logits on demand;
  this fallback adds work and is not a claimed sampled-chat optimization.

All five arms (options off, recurrence, projections, fused head, layout-only)
passed five API smoke checks each: greedy, sampled logprobs, penalties, return to
greedy, and a forced tool call. These are correctness checks, not speed results.
Only CUDA SM75 has been built/tested; these prototypes are not an upstream-ready PR.

## Reproduction

Use `run.py` for a single arm and `sweep.py` for sequential isolated runs. Both
use the protected production profile copied to ignored runtime storage, an
independent expert-profile copy per server, and localhost port 8087. The ordinary
speed suite uses three runs with thinking off; scored Pi tasks force thinking on.
`summarize.py` publishes aggregate counters without requests or model output.

Experimental switches are `STRATA_YUKON_COMMIT=1` plus
`STRATA_YUKON_COMMIT_SPLIT=1`, `STRATA_YUKON_PROJECTIONS=1`,
`STRATA_YUKON_HEAD=1`, and the separate control `STRATA_YUKON_HEAD_LAYOUT=1`.
All default off. Do not enable them in production from the kernel results alone.
