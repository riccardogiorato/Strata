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

## Status

Build and validation in progress. No new performance or quality claim yet. No change to production settings.
