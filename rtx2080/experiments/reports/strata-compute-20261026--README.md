> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata compute speedups on RTX 2080

The four requested areas were tested at long context. The useful change is native expert prefill fusion on Turing: **1.103× prompt throughput**, with cold prompt time falling from **151.92 to 137.71 seconds**. No repeatable decode improvement was established. The installed executable and production recipe were preserved during benchmarking, then updated in the follow-up deployment below.

The subsequent normal-configuration comparison (`../strata-production-ab-20261026/README.md`) superseded the minimal deployment with the fully tested tuning profile. It measured the actual normal settings, all six 122K edits, and both full AG-Bench suites.

## Production deployment after validation

The follow-up deployment installed the exact tested `strata-fused-sm75` executable at the normal engine path and enabled the three prefill fusion flags in `recipes/strata-configs/strata-swift15-iq2xs-gsq-023-tailnet.json`. All other production configuration values were preserved, including vision, network settings and context capacity. The normal configuration uses its existing automatic prefill/cache sizing rather than the benchmark's fixed sizing; the measured percentage above applies to the benchmark configuration.

The change takes effect on the next normal Strata start. Bolt was running when deployed and was left running. `deployment.json` records hashes and the rollback executable; `deployment-before.json` preserves the prior configuration. `final-state.json` remains the historical state at the end of the benchmark, before this deployment.

## Controlled coding result

RTX 2080 8 GB, i5-9600K, 64 GB RAM; Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS. Strata 0.2.3 / native engine 0.1.48 with existing local Turing, prefill-loan and session-cache patches. All GPU tests used 165 W. Capacity was 131,072 tokens; this task supplied **122,451 input tokens**, with no cached prefix, and returned 1,433 output tokens.

Four fresh engine launches ran baseline, fused, fused, baseline. The same `strata-tab` binary was used in both arms; only the three prefill flags changed. Direct pointer-table mode and experimental verification fusion were off. Model startup, roughly 16–19 seconds, is excluded. Both arms used effective prompt chunk 4,096.

| Measurement | Baseline mean | Fused mean |
|---|---:|---:|
| Prompt throughput, total tokens / total prompt time | 806.0 tok/s | 889.2 tok/s |
| Cold prompt processing | 151.92 s | 137.71 s |
| Full request | 176.79 s | 163.44 s |
| Generation during these requests | 58.1 tok/s | 56.1 tok/s |

That is **9.4% less prompt time** and **7.5% less full-request time** on this fixture. All four outputs matched the expected full-file Python AST after changing integer literals 1024 to 2048. Formatting can differ; output bytes are not claimed identical. Generation in these runs was slightly slower with fusion, so the benefit is in prefill and total request time. This is a narrow deterministic edit, not an agentic coding quality benchmark. Two samples per arm support a local repeated result, not a confidence interval over all workloads.

## What happened in each of the four areas

1. **Expert prefill kernels.** Built and enabled Strata's existing pointer-table MMQ path, which can read resident expert weights without gathering them. Its adapted SM75 unit test passed 890 bitwise comparisons. The full cold retrieval screen was slightly slower: 804.9 versus 815.4 tok/s. Keep it off. The fused kernel experiment below was the useful expert-compute change.
2. **Turing-compatible fusion.** Added opt-in native codebook support using the smaller WW=2 tile. The original WW=4 codebook setup can exceed Turing's 64 KiB shared-memory limit. One fused path combines gate/up work, activation processing and down projection. At a 4,096-token chunk, isolated IQ2_S/Q2_0 layers improved from 31.538 to 20.253 ms (1.56×), and IQ2_XXS/Q2_0 from 26.622 to 18.653 ms (1.43×). Whole-model gains are the smaller repeated figures above. No model weights were changed.
3. **Cheaper speculative verification.** Screened recurrent-state split, existing activation/shared-expert/final-mixer fusion, and serial shared-expert scheduling. Implemented guarded cross-stream reuse of an existing q8 activation image. Once correctly activated on CUDA, both the existing QFUSE control and the new reuse variant produced malformed code at 121K context. They are rejected; the new reuse change was removed from the working source. A short deduplication test passed even on those broken long-context paths, demonstrating why that smoke alone was insufficient.
4. **CPU/PCIe/GPU overlap.** Tested existing adaptive overlap and raising the PCIe fraction from 0.35 to 0.5. Neither won. The long-prefill diagnostic spent only 0.7% of measured GPU timeline waiting for expert copies; transfer overlap alone was not a large opportunity on this fixture.

## Decode screens and rejected results

Each valid speed screen restored the same 120,999-token coding prefix, processed seven new tokens and generated 2,048 tokens. These are single screens, not repeated winners or complete-module correctness tests.

| Configuration | Generation |
|---|---:|
| Baseline | 51.7 tok/s |
| GDN split | 52.5 tok/s |
| Shared expert serial plus quantization deduplication | 52.7 tok/s |
| LFUSE plus final mixer fusion, HC inactive | 52.0 tok/s |
| Adaptive overlap | 51.3 tok/s |
| PCIe fraction 0.5 | 50.6 tok/s |

The small split/serial differences were not promoted as speedups. Instrumented decode put CPU expert work at about 24.35 ms per verification window and draft work at 3.43 ms; verifier profiling disables the shared-expert stream, so these are diagnostic costs rather than an unchanged baseline measurement.

The portable CUDA QFUSE control stopped after 454 tokens of malformed Python. QFUSE plus new shared-q8 reuse stopped after 73 tokens without an implementation. Their short request times are **failures, not speedups**. The control already failed without our reuse patch, so these observations do not isolate the root cause to the new code. Both remain disabled.

Two harness corrections are retained in the evidence. The first decode screen used a retrieval snapshot too late to match the coding request and recomputed the prefix; it is excluded. A later reuse screen used `STRATA_QFUSE_HC`, which is HIP-only and inactive on CUDA; the activation assertion caught it. Its apparent 56.6 tok/s is excluded as evidence for reuse. Corrected runs used `STRATA_QFUSE` and exposed the long-output failures. `summary.json` marks these exclusions explicitly. The screen harness now checks prematurely completed long modules for syntax and presence of implementation before running the short smoke.

## Coverage and validation

- Native fused reference tests passed for every supported format pair, including uneven expert groups, zero work and scatter placement. These are tolerance-based comparisons against an int8-rounded mathematical reference and FP32 reference; fusion is not claimed bitwise equivalent to MMQ.
- Pointer-table tests passed all 890 bitwise comparisons, but the full-model timing did not improve.
- Five long retrieval checks passed; all four 122K full-file edit AST checks passed.
- All twelve recorded short executable-code checks passed. The two explicit long-code failures and one inactive-feature activation failure remain visible separately.
- The new fused path covers 45 of this pack's 48 expert layers. Three IQ1_M layers still use fallback. An 8,192 chunk request automatically fell back to 4,096 because those layers prevent the smaller all-fused buffer layout. No larger-chunk speedup is claimed.
- This is CUDA SM75 validation. HIP, SYCL, vision and a full agent benchmark were not rerun. The next concrete prefill research target is the three remaining IQ1_M layers; whether covering them makes 8K chunks faster is unmeasured.

## Use the selected profile

`cached-profile.json` points to the private **`strata-fused-sm75`** binary, with only these new flags:

```text
STRATA_PF_FUSED=1
STRATA_PF_FUSED_SM75=1
STRATA_PF_FUSED_SM75_IQ=1
```

That binary was built before the rejected shared-q8/direct-MMQ experiments and passed its own 121K cold retrieval and executable-code checks. The ABBA comparison used the later binary with those extra paths disabled, sharing the same fused kernel source. The retained executable also includes the earlier cache improvements. `history-edit-profile.json` carries the same kernel settings into the earlier dense-checkpoint profile; that combination was not separately benchmarked here.

From the repository root, after stopping the other GPU inference server:

```bash
python3 experiments/strata-overnight-20261026/launch_cached.py \
  --config experiments/strata-compute-20261026/cached-profile.json \
  --cache-dir "$HOME/.cache/strata-ssd-sessions" \
  --engine-dir ../strata-023 \
  --python ../strata-023/.venv314/bin/python \
  --auto-pin
```

The cached API uses `http://127.0.0.1:8088/v1`; a stable `X-Session-ID` identifies each conversation. The launcher and machine-specific paths are from the earlier cache campaign (`../strata-overnight-20261026/README.md`). This campaign does not establish that cache and compute speedup factors multiply.

## Evidence and rollback

`sm75-iq-fusion.patch` (also `native-compute.patch`) contains only the retained native delta against the existing modified checkout. `rejected-shared-q8-reuse.patch` preserves the removed experiment. `provenance.json` records executable, source and patch hashes; source backups and binaries remain local and ignored by Git. The exact upstream base is `5c8dd322528cc84f68f461ad54a506b9da8fa8d4`, plus the preexisting local patches recorded by the earlier campaign.

`results.jsonl`, responses and engine logs are the raw evidence. Run `python3 experiments/strata-compute-20261026/summarize.py` to regenerate the summary. `final_trials.py` describes the ABBA fixture; it originally also ran the now-rejected QFUSE screens. Replaying it unchanged now stops at their long-code quality gate. For new ABBA measurements, omit those rejected screens and recreate the coding snapshot with `screen.py seed` if decode probes are wanted.

The installed executable, production recipe and expert profile hashes are checked in `final-state.json`. Temporary benchmark snapshots are removed after their sizes are recorded in `cleanup-manifest.json`. No production defaults, commit or push are part of this campaign.

The implementation audit drew on [TensorFold's CUDA recipes](https://github.com/ashhart/TensorFold/blob/main/docs/recipes/cuda.md), [Rapid-MLX](https://github.com/raullenchai/Rapid-MLX), and local Strata source. The patch adapts Strata's existing CUDA kernels; no Apple Metal kernels were copied.
