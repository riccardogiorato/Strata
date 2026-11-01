# Compact fused-prefill follow-up — November 1

**Rolled back at the user’s request.** The previous production binary and profile are restored. This configuration remains experimental on `experiment/compact-prefill`; the measurements below are unchanged. [Compact evidence](compact-results.json).

The earlier single failed edit was not sufficient evidence that compact buffers corrupt the model. Repeating the test exposed numerical variation in the unchanged baseline too. We isolated the observed probe variation to automatic CPU/GPU sharing on a six-token prompt suffix and added an opt-in minimum chunk size for that sharing. This does not establish the cause of every model mistake or guarantee deterministic generation.

Same RTX 2080 8GB / SM75 / 165W, i5-9600K, 64GB RAM and Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS 125B weights. Capacity stays 131,072 with 32,768 resident INT8 KV tokens. Routing prior 1.5, MTP spec4, requested prefill chunk 4,096, existing VRAM loans, RAM session cache and loop closure remain enabled. Raw private prompts, responses and traces remain under ignored runtime storage; compact-results.json contains aggregate evidence.

## What changed

`STRATA_PREFILL_CPU_SHARE_MIN=16` keeps actual prompt chunks smaller than 16 tokens on the GPU. Larger chunks retain the existing automatic sharing policy. The new option defaults to 0, preserving the old eligibility condition. It does not change routing, model weights or fused kernel arithmetic.

The compact candidate also sets `STRATA_PF_FUSED_LEGACY_LAYOUT=0`. That permits the already-implemented smaller fused buffers and the native fused ring of 512 slots. IQ1_M fusion stays enabled and FP16 WMMA stays disabled. At the requested 4,096-token startup chunk, the measured prompt loan falls from 1,898 expert-cache slots with the old layout to 1,789 with the compact layout. Compact buffers with a 384-slot ring borrowed only 1,657 slots but were tested separately and offered no speed advantage. Smaller buffers alone therefore did not guarantee higher throughput.

## Numerical investigation

- Six fresh-engine 122,451-token edits, in control / compact / compact384 / compact384 / compact / control order: control 2/2 passed at 878.38 tok/s; compact 2/2 at 885.21 (+0.78%); compact384 1/2 at 877.09. The failed edit omitted the same two integer literals as the earlier failure. All runs used the same expert-profile seed.
- Four 10,254-token diagnostic probes with automatic sharing: recorded expert IDs and BF16 routing weights agreed through the large prompt segments. Differences appeared in the final six-token segment at position 10,247, including within the unchanged control. Full FP32 first-token logits varied too.
- Disabling CPU sharing only for diagnosis made all six pairwise first-logit comparisons and recorded routing traces identical across both layouts. Automatic sharing selects a CPU/GPU split using timing feedback; the arithmetic can therefore differ between repeats.
- Three probes with the new minimum of 16 matched the GPU-only reference exactly. A separate optional kernel diagnostic regrouped identical inputs four times per tested format pair (IQ1_M/Q2_0, IQ2_XS/Q2_0 and two IQ2_S down-projection formats); every normalized output value matched, and all numerical reference checks passed.
- With minimum 16 on both layouts, a four-run 122K control / compact / compact / control comparison passed 4/4 exact AST edits. All six first-logit comparisons matched. All AST hashes matched; one response had an additional final blank line, so raw file hashes were not all identical.

The sparse residual dump was empty after the final tiny segment and was not used as evidence. Routing traces record BF16 weights, not every internal activation. The equality result is specific to these probes.

## Throughput

Rates divide total native tokens by total native time.

| Workload | Control | Compact + minimum16 | Change |
|---|---:|---:|---:|
| 122,451-token exact edit, minimum16 on both arms | 876.73 | 884.92 | +0.93% |
| 32K standard prefill | 889.02 | 918.92 | +3.36% |
| 16K standard prefill | 875.56 | 903.74 | +3.22% |
| 4K standard prefill | 657.52 | 641.47 | −2.44% |
| Short chat decode | 59.16 | 57.75 | −2.38% |

The 122K row isolates layout with minimum16 shared by both arms. The standard suite compares the installed production executable/profile against the combined candidate, three repeats per case. It completed without failures or skipped cases. Those rows are different workloads, not interchangeable context-scaling measurements. Short chat generated 900 tokens on each arm; draft acceptance was 474/608 (77.96%) on the control and 470/622 (75.56%) on the candidate. The lower acceptance coincided with the slower chat decode, without establishing it as the sole cause.

The synthetic cached-conversation case reused 68.90% versus 68.96% of all input tokens; median continuation TTFT was 5.467 versus 5.433 seconds. Native decode was 55.83 versus 55.04 tok/s with different generated lengths. This synthetic section is separate from scored Pi coding and near-capacity continuation reuse.

## Expert-cache allocation observation

In the standard suite, repeated large-prefill loans restored 1,476 cache slots on the control and 1,106 on the compact candidate. Both requested 1,788 MiB for deferred decode restoration. The cache uses 512 MiB physical segments; a roughly 16 MiB free-memory difference crossed a segment boundary. Actual free memory after resizing was 1,288 versus 1,784 MiB before reloading decode resources. The candidate first lost the additional 16 MiB immediately after capturing a five-token verifier graph during the synthetic conversation case; the control did not capture that window there. Both arms had identical free memory at startup and during the preceding 16K cases. Graph-dependent memory is therefore a hypothesis, not an established compact-buffer overhead or proof of a throughput cause. The verifier already destroys its captured graph executables at the repeat-loan boundary; this investigation did not measure which allocator retained the difference. The first cold near-capacity requests retained 1,476 slots on both arms. No reserve reduction or cache-sizing change was made during this validation.

## Final coding validation and decision

Near-capacity sessions completed in control / candidate / candidate / control order. Both arms passed 4/4 independent file checks. Cold initial prefill was 873.09 versus 880.72 tok/s (+0.87%); all-request native prefill was 808.30 versus 819.63 and decode 60.58 versus 61.62. Expert-pool hits were 80.05% versus 80.62%; resident shares of all routed experts were 75.13% versus 75.77%. Continuation prefix-token reuse was 99.751% versus 99.818%, with a hit on every continuation request. Largest prompts were 123,079 and 124,413 respectively. The candidate generated 7,946 tokens versus 5,513, so its longer wall time is not evidence of slower decoding. All API/native usage counters reconciled.

The scored suites completed in control / candidate / candidate / control order:

| Scored coding, same ten tasks twice per arm | Current control | Compact + minimum16 |
|---|---:|---:|
| Independent task passes | 20/20 | 20/20 |
| Native prefill tok/s | 331.42 | 352.19 |
| Native decode tok/s | 62.20 | 61.11 |
| GPU-generated tokens | 57,488 | 52,532 |
| Expert-pool hit rate | 80.00% | 80.04% |
| Resident share of all routed experts | 75.14% | 75.19% |
| Continuation prefix-token reuse | 93.10% | 91.80% |
| Continuation requests with a cache hit | 100% | 100% |
| Maximum prompt tokens | 21,556 | 13,801 |
| Total task wall seconds | 1326.9 | 1230.0 |

All native/API counters reconcile. Per-task summaries are included in `compact-results.json`. The candidate's scored prefill rate is +6.27%, while decode is -1.74%. The lower total task time includes fewer generated tokens and different tool paths; it is not a pure engine speedup. The lower aggregate continuation-token reuse also reflects different history lengths and paths: both arms hit the cache on every continuation request.

**Original decision, subsequently reversed:** compact buffers plus minimum16 were briefly selected for the long-context production profile. The modest long-prefill gain repeated in isolated edits, the standard suite and near-capacity agent sessions. Both final arms passed all scored checks. This is a tradeoff, not an across-the-board speedup: scored coding decode was 1.74% lower and the short chat/4K probes about 2.4% lower. There is no claim that the small sample proves unchanged general model quality. The 384-slot compact variant remains unselected; FP16 WMMA remains off.

The candidate executable is retained for research. `rtx2080/CURRENT.json` records its historical installation and the completed rollback. Production again uses `STRATA_PF_FUSED_LEGACY_LAYOUT=1` without `STRATA_PREFILL_CPU_SHARE_MIN`. The restored profile comes from `fcc1adff233f8d31a2ecf18c4d457a7061048721` and the saved executable `runtime/bin/strata-before-compact-20261101`, with the service stopped during restoration. The minimum16 native change and its diagnostic test are also restored to the pre-experiment production source; the experimental branch preserves them. Routing prior 1.5, MTP, 128K capacity, vision, PCIe settings, session caching and the existing loop closure are retained.

## Reproduction and limits

Baseline profile/source state: fcc1adff233f8d31a2ecf18c4d457a7061048721; installed native source e9fe9e763d9f7b69826c990058e49f89dafeef71, executable SHA256 2698152f7ab0e08f1246d7d28b1d674f3a1746bc788e005538ff02d1347962e3. Candidate native source 2d336aa01b52d178983e6e233f405dcdc219a042, executable SHA256 82b17faf7223dc34ea93f3e31c76b8c6af5f5462af2354ca1e019a52cae23602. Boot metadata records the harness checkout separately from the executable source; the hashes identify which native engine actually ran.

The prepared local harness uses pinned Pi 1.4.0, thinking enabled, temperature 0 / seed 42 at the API, sandboxed workspaces and independent file verifiers. Scored suites repeat ten tasks twice per arm. Near-capacity sessions disable compaction and test file editing, retrieval, tool use and resumption. Agent token rates depend on the generated task path and are not isolated kernel measurements. Fixed sampling settings do not guarantee identical replies: automatic CPU sharing remains active for eligible larger chunks, and residency-biased routing remains enabled. The minimum16 probe equality does not establish deterministic generation for arbitrary conversations.

An initial near-capacity launch missed the resource-measurement wrapper: four sessions exited before any API/native requests. They are recorded as invalid harness runs, not model failures or passes. The wrapper was restored, prerequisites checked, and the four sessions rerun under new labels.

CUDA SM75 was built and tested. HIP, Windows and other GPUs were not tested. No upstream PR or comment was changed by this follow-up. No new TensorFold code was copied: this extends the local Strata investigation documented in README.md.

Local scripts: compact.py, validate_compact.py, analyze_compact.py and export_compact.py. They require private prepared fixtures, installed model assets and the frozen baseline hashes; they are not a standalone public benchmark. Never run against the live production service. Changing the deployed baseline requires preparing new hashes and labels rather than bypassing protection checks.
