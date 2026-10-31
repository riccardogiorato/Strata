> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata 0.2.8 upgrade — RTX 2080, 2026-10-30

Upstream main `870aedd9e1ebe1c91f94da93b59af17729f6c5c0` (Terminal 0.2.8 / engine 0.1.54),
with the same 17-file production tuning carried forward in `6cb7e0910a9552b748e6c743dcd18b8e3a079728`.
Old production engine: `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d` (0.1.52).
Candidate executable SHA-256: `0c688198df3e319d7213748428dae75c874282e33b946b2fb7c23f4e01435c4b`.

RTX 2080 8GB, i5-9600K, 64GB RAM, 165W. Same Swift 1.5 Flash-Next IQ2_XS model,
profile seed, 131072-token capacity, 32768 resident int8 KV, requested 4096 prefill,
PCIe fraction 0.35, spec4/min-p0.70, routing prior1.5, KVA0, fused native-IQ kernels,
VRAM prefill loans and 8GiB/two-slot RAM session cache. Text-only benchmark servers;
production retains CPU vision. No SSD page cache or new IQ1_M prefill flag enabled.

## Same-day performance

Rates are total newly read/generated tokens divided by native prefill/decode time.
Thinking tokens count. Wall/TTFT include overhead; they are not raw kernel rates.
Three-repeat standard speed suite per arm; two fresh-process 121K cold and warm
requests per arm (latest/base/base/latest). One 0.2.8 natural 11-task agent suite and a repeated 0.2.7 control. The initial
0.2.7 control overlapped CPU-heavy rendering work; its full results are retained
under `initial_agent_control` in summary.json and excluded from the headline
rate comparison. CPU process observations are retained in the telemetry logs. The repeat avoids
the heavy rendering, but a brief unrelated service startup also caused a CPU
spike during task3. Treat agent rates as descriptive, not an isolated causal
speedup. The unaffected standard speed and 121K tests are the primary
throughput regression checks.

| Metric (tok/s unless named seconds) | 0.2.7 tuned | 0.2.8 tuned | Change |
| --- | ---: | ---: | ---: |
| 4K prefill | 655.90 | 658.94 | +0.46% |
| 16K prefill | 880.76 | 868.49 | -1.39% |
| 32K prefill | 886.61 | 881.95 | -0.53% |
| Short chat decode | 56.65 | 57.23 | +1.03% |
| 121K cold prefill_tps | 843.67 | 844.77 | +0.13% |
| 121K cold ttft_mean_s | 143.68 | 143.48 | -0.14% |
| Scored agent prefill_tps | 325.20 | 339.91 | +4.52% |
| Scored agent decode_tps | 55.62 | 59.22 | +6.47% |

## Agent checks and cache

Ten scored tasks: **10/10 → 10/10**.
Task8 already passes before edits; retained in raw results and full-runtime totals.
Scored output tokens: 23292 → 26325.
Scored runtime: 591 → 639 seconds.
All eleven tasks' runtime: 762 → 842 seconds.
Prefix token hit: 87.80% → 89.06%.
Expert pool hit: 80.22% → 80.08%.
Direct PCIe share of routed experts: 6.01% → 6.00%.
API errors: 0 → 0; fixture violations: 0 → 0.
Every native output/input/cache token count is checked against its Pi usage row.

Agent trajectories can differ; token-rate changes and task quality matter more than
wall time alone. One suite is a regression check, not broad quality equivalence.
Actual agent history lengths and per-task rates are in summary.json; capacity is
128K, but ordinary tasks are not padded. Separate long probes use ~121K inputs.

## Validation and PR

- 1,241 Python server tests passed; 17 skipped.
- conversation_file, conversation_memory, session_save_reclaim tests passed.
- PR #4642 merged main870aedd, CUDA rebuilt, enabled/disabled IQ1_M CTests passed.
- IQ1_M 4K/8K layer parity passed with unchanged output hashes; earlier full-model
  PR speed measurements remain pinned to their original revisions.
- Draft PR: https://github.com/Niko1221/Strata/pull/4642 (head770cba2).
- HIP/SYCL/other GPUs not tested. No broad cross-model claim.

## Evidence and rollback

`summary.json`, `provenance.json`, `results.jsonl`, per-arm engine/server logs,
standard speed results and frozen agent fixtures retain all individual runs.
`local-tuning.patch` is the exact local integration delta from pinned upstream.
`private/` retains original configs and service/wrapper backups.

After deployment, restore the old service, CLI and monitor with:

```bash
bash experiments/strata-028-upgrade-20261030/rollback.sh
```

## Deployed state

The normal `strata-serve.service`, CLI shortcut and monitor now use
`../strata-028-custom` and the new `strata-swift15-iq2xs-gsq-028-tailnet.json` config.
Live validation passed authenticated generation and a structured tool call;
unauthenticated model access returned 401. Health confirms 131072-token capacity,
loaded model, API authentication and image support. The running GPU executable and
all production tuning environment flags match the tested candidate. CLI is 0.2.8.
Existing CPU vision config was preserved; new image inference was not tested.

The scored agent suite took 591 → 639 seconds (+8.1%) and generated
23292 → 26325 tokens (+13.0%). Do not read this as an end-to-end latency gain.
All eleven tasks took 762 → 842 seconds. The main conclusion is preserved token
throughput and passing regression checks, not faster task completion on every run.

Deployment record: `deployment.json`. Old source, binary and config are retained.
