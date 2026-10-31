> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Swift: Strata 0.2.3 versus 0.2.6 on RTX 2080

## Result

No material long-context prefill or first-output latency improvement was demonstrated by this update. Keep the existing setup for now; this speed test does not establish a coding-quality improvement. Project Maya could not be included because its current engines support GLM and DeepSeek, not Swift/Qwen. The earlier suggestion of a three-way Swift comparison was incorrect.

## Measured latency

Means of two fresh boots per version, in old → new → new → old order. TTFT is wall time to the first nonempty streamed content or tool-call delta. Cold means no matching conversation prefix, not an emptied OS file cache.

| Workload | Actual input tokens | Old TTFT, s | New TTFT, s | New vs old | Old prefill, tok/s | New prefill, tok/s |
|---|---:|---:|---:|---:|---:|---:|
| 32k-cold | 32,879 | 56.16 | 56.22 | +0.1% | 587.6 | 585.8 |
| 32k-followup | 33,037 | 1.50 | 1.61 | +7.3% | 113.0 | 105.7 |
| 64k-cold | 65,665 | 110.97 | 110.93 | -0.0% | 592.6 | 592.8 |
| 64k-followup | 65,823 | 2.04 | 2.01 | -1.5% | 84.0 | 87.6 |
| 120k-cold | 121,834 | 205.01 | 205.32 | +0.2% | 595.0 | 593.8 |
| 120k-followup | 121,992 | 2.13 | 2.17 | +1.8% | 80.7 | 79.2 |

Follow-up prompt rates cover only the 165 newly read tokens; most of the conversation is reused. They must not be compared directly with the full cold-prefill rates.

## Decode: output-dependent, not an equivalent-work speed ranking

The request cap was 512 output tokens. Many responses ended early with tool calls despite a request for code. The old and new builds generated different outputs, including different lengths; neither output equivalence nor a quality ranking is established. Pooled decode below is total emitted tokens divided by total engine decode time within each row.

| Workload | Old decode, tok/s | New decode, tok/s | Old output lengths | New output lengths |
|---|---:|---:|---|---|
| 32k-cold | 41.8 | 48.0 | [57, 29] | [62, 62] |
| 32k-followup | 45.9 | 49.9 | [43, 42] | [42, 40] |
| 64k-cold | 48.4 | 47.2 | [27, 61] | [49, 28] |
| 64k-followup | 37.9 | 49.2 | [41, 41] | [27, 41] |
| 120k-cold | 48.4 | 45.3 | [28, 512] | [512, 224] |
| 120k-followup | 47.2 | 37.7 | [39, 38] | [39, 41] |

The near-128K cold samples varied between code and tool calls, including across repetitions of the same build. Neither the speed of those unequal answers nor apparent instruction-following differences should be promoted as a general engine win. All emitted tool-call argument payloads were parsed and checked as JSON; this is only a protocol check.

## Configuration and scope

- RTX 2080 8GB, i5-9600K, 64GB RAM; fixed 165W during measurements.
- Existing Swift 1.5 Flash-Next IQ2_XS shards, same tokenizer and initial expert profile. No model redownload or requantization.
- 131,072-token capacity, 32,768 resident KV, int8 KV, MTP spec4, spec-min-p 0.70; same existing adaptive/cache settings.
- Old: Strata 0.2.3 commit `5c8dd322528cc84f68f461ad54a506b9da8fa8d4`, existing `build-turing-pr3281/strata`.
- New: Strata 0.2.6 commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`, Qwen engine release version 0.1.50, source-built for SM75.
- Both use the same existing local Turing QSA kernel patch and environment knobs. The new arm is therefore a tuned source build, not the stock downloadable binary.
- Each version uses its own server. The old server has existing local harness fixes. This is a serving-stack comparison, not an isolated single-kernel comparison.
- Frozen repository-based coding histories: proportional shortening of tool results for 32K/64K; full history near122K. Fixed synthetic follow-up tool result, identical across arms, rather than inserting each arm’s different output.
- Greedy requests with thinking disabled; one short excluded warmup per boot. Real agent quality and long thinking runs were not tested.
- GPU measurements were serial, after compilation finished; OS page cache was not flushed.
- New-build logs enabled automatic asynchronous-tier selection but logged no switch into that tier during these requests. This does not test its possible gain in a longer sustained-generation session.
- No unsupported Swift load was attempted in Maya and no Maya speed was invented. [Project Maya v1.1.27](https://github.com/mw00/project-maya/tree/v1.1.27).

## Evidence and restoration

- `method.json`, `workloads.json`, `prepare.py`, and frozen `*-cold.json` / `*-followup.json`: inputs and method.
- `run.py`, `results.json`, `summary.json`: execution and measured values.
- `*.response.json`, `*.engine.log`, `*.server.log`, `output-audit.json`: responses, cache reuse, runtime behavior and protocol checks.
- `turing.patch`, `configure.log`, `build.log`, `binary-hashes.json`: build provenance.
- `original-state.json` and `restore.json`: original server/power state and restoration results.
- No permanent service/configuration upgrade was performed. Bolt was restored; the previously inactive Strata service remains inactive.
