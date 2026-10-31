# IQ1_M on the current RTX 2080 configuration

This campaign integrates the opt-in IQ1_M/Q2_0 adapter from PR #4642 into the October 31 `rtx2080` profile, based on Strata 0.2.9 / engine 0.1.55. The production binary remains unchanged until a candidate passes both performance and correctness checks.

The adapter extends Strata's existing compressed-weight int8 fused prefill. TensorFold's tiled quantized prefill and expert-stage memory sizing inspired the investigation; no TensorFold kernel was copied. It covers the three remaining IQ1_M layers in our mixed Swift IQ2_XS weights, and enables the existing fully fused buffer layout when all layers qualify.

## Protocol

- RTX 2080 8GB at 165W; same Swift weights and immutable expert-profile seed per fresh process.
- 131,072 context capacity, 32,768 resident INT8 KV, routing prior 1.5, spec4, existing production prefill loans and other settings.
- Compare the installed production binary, the integrated binary with the new flag off, and that same binary with the flag on.
- Fixed-4K cold-edit sequence: production / off / on / on / off / production. The fixture has 122,451 input tokens, temperature zero, seed 1234, thinking off. Score AST equivalence of the entire requested edit; retain failed outputs.
- A separate 121K retrieval fixture has cold and reused-prefix requests. The usual speed suite covers chat and shorter prompts too.
- Test auto chunk sizing separately, recording the actual selected chunk rather than the requested ceiling.
- Pi agent tasks use thinking enabled at the API, unchanged tool schemas, isolated workspaces and sandboxed independent verification. Record tokens/time, expert-cache hit counts, prefix reuse and scores. Ordinary suites retain compaction; explicit near-capacity tool tests disable compaction so the model actually sees the large prompt.
- Kernel checks include independent numerical reference, opt-out checks, 4K/4.5K/8K routed batches, CUDA memcheck and the existing IQ2_S/IQ2_XXS paths.

Scripts live here; raw inputs, outputs and configs stay under ignored `runtime/iq1m-20261031/`. `campaign.py` consumes a resolved production config and the archived edit/retrieval fixtures there. `harness.py` adapts our previously pinned Pi/fx benchmark harness; tasks and local harness executables come from the existing `local-ai-rtx2080` benchmark workspace. The shared proxy explicitly enables thinking despite Pi's local reasoning metadata.

## Implementation findings (validation still in progress)

- The integrated INT8 adapter passes numerical tests, opt-out checks and CUDA memcheck. All 46 existing fused device functions retain identical assembly; one IQ1_M function is added.
- In the first 122K series, installed production averaged 858.1 tok/s (2/2 exact edits), the rebuilt feature-off control 852.3 (2/2), and feature-on 881.2 (1/2). A rendering job overlapped portions of the series; final performance claims need clean confirmation. All outputs had 1,433 tokens. The failed edit missed two literal replacements.
- `STRATA_PF_FUSED_LEGACY_LAYOUT=1` is a diagnostic added here: keep the old ring/buffer plan while using supported fused kernels. Two runs at 877.7 and 873.3 tok/s passed both edits. This does not establish general quality equivalence.
- The existing FP16 grouped path (`STRATA_PF_WMMA=1`) failed to launch IQ tiles on the RTX 2080: its 84,992-byte shared-memory tile exceeds the 65,536-byte device limit. This campaign adds a 64-weight-row / 8-warp tile using 51,200 bytes, retaining FP16 weights/activations and FP32 sums. Devices where the original tile fits retain it; the already-fitting Q2_0/IQ4_NL-down tiles retain their shapes. Device attributes are initialized once per device.
- Before that fix, the existing WMMA parity test failed to launch six of eight cases; afterwards all eight pass. CUDA memcheck reports zero errors. The first full-model FP16 run passed the edit at 875.9 tok/s.

No production settings have changed. Chunk tuning, matched final controls and full agentic validation remain to be completed. The FP16 tile fix is an extension of upstream Strata's Volta kernel, separate from PR #4642's INT8 adapter. Neither is copied TensorFold code.

### Additional tuning screens

Automatic prefill (`auto:8192`, lend 100%) selected 4,352 tokens for FP16 and 4,608 for compact INT8. At 122,451 input tokens, FP16 measured 870.0 tok/s, FP16 with upstream embedding reuse accounting 860.1, INT8 with legacy layout 864.4, and compact INT8 888.3. All four exact edits passed. These are single screening runs, not paired final claims; the compact path's earlier failure remains part of its record.

An opt-in `STRATA_PF_WMMA_NT=512` variant doubles the narrow tile's warps while retaining its 51,200-byte shared allocation and FP16 arithmetic. In the synthetic 693-row / seven-expert reference fixture, IQ1_M decreased from 0.4838 to 0.4169 ms per call (100 GPU-timed calls). Both thread layouts passed all eight numerical cases, including finite-output checks. This is a kernel microbenchmark, not an end-to-end speedup claim. Full-model and agent checks determine promotion.
