> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Persistent prefix pages on RTX 2080

**Implemented on a separate branch.** At 121K input tokens, cold restart recovery fell from **144.2 to 10.5 seconds** across two reversed-order pairs. A real read/write/test coding task with one deliberate restart passed in both arms: **359.9 → 244.7 seconds**. This is cache recovery, not a faster decode kernel. New histories cost more to save.

Branch `engine/persistent-prefix-cache` is in `private/source`, code commit `b06c603`, based on frozen production v0.2.7 plus existing local tuning (`c1e013a`). The separate TensorFold-inspired contribution is [draft PR #4642](https://github.com/Niko1221/Strata/pull/4642); its IQ1_M patch is not included here. Installed production binary/config/profile are protected by hash checks.

## Matched long-context requests

RTX 2080 8 GiB, i5-9600K, 64 GB RAM, Samsung 970 EVO NVMe, driver 615.78.08, CUDA 13.4.92, 165 W. Swift 1.5 Qwen3.8 Flash-Next IQ2_XS, context capacity 131072, resident KV 32768/int8, prefill 4096, PCIe fraction 0.35, existing fused-IQ kernels and VRAM loans retained. Same executable/model/profile/sampling within each pair. Every request had about 121K actual input tokens and produced the requested Python function; all 32 long checks passed, plus three smoke checks.

Both arms use `--prompt-cache 20 --prompt-cache-every 8192`, `STRATA_SESSION_ALL_CHECKPOINTS=1`, native conversation RAM 8192 MiB/two slots. Persistence adds 1024 MiB hot pages and a 24576 MiB SSD quota. These denser checkpoint settings are common experimental settings, not an unchanged installed-production comparison. Order: base / pages / pages / base. Means and individual-run ranges follow; wall time includes synchronous persistence before final SSE completion.

| Scenario | Persistence off, seconds | Persistence on, seconds | On / off |
| --- | ---: | ---: | ---: |
| First cold history | 143.306 (142.752–143.860) | 158.151 (157.935–158.366) | 1.104× |
| New related branch | 40.673 (39.918–41.265) | 50.249 (49.473–50.962) | 1.235× |
| Return to evicted branch | 40.569 (40.502–40.636) | 11.256 (7.569–14.943) | 0.277× |
| Repeat in native RAM | 0.721 (0.709–0.734) | 0.427 (0.403–0.452) | 0.592× |
| Restart, cold SSD pages | 144.222 (143.804–144.639) | 10.471 (10.007–10.935) | 0.073× |
| Edit middle of history | 79.998 (79.820–80.176) | 88.395 (88.245–88.546) | 1.105× |

Restart requests reused 121009/121016 tokens instead of zero. Before each restart, only this experiment's page files were flushed and evicted from the OS cache; `fincore` reported zero resident bytes. Startup time is excluded from this request table. Evicted-branch recovery varied from 7.6 to 14.9 seconds; one process swapped up to 3.64 GiB. Native-hot requests avoid SSD restore. Middle-history edits reused 57344 tokens in both arms, so persistence only added save cost there.

Creating snapshots adds roughly 9–14 seconds. Four branch snapshots represent 14.96 GB logical state using 6.84 GB physical pages plus 2.1 MB manifests (about 54% less storage). The 1 GiB page LRU is too small for a 3.74 GB snapshot; memory-budget tuning is reported separately. `summary.json`, `results.jsonl`, request/response files and native/server logs retain the evidence. Prototype/aborted pre-final-build records under `prototype-smoke` are excluded. An interrupted first speed arm is archived under `interrupted-speed`; both speed arms were restarted after the UI interruption.

## Actual coding task with restart

The model inspected two files, repaired interval merging, ran immutable tests and reported completion. It had about 121K tokens of reference context, thinking enabled, temperature zero, seed 42 and the same restart after its first file reads. Both arms used four turns/four tool calls and passed all tests. Execution was isolated with bwrap; tests were unchanged.

| Metric | Persistence off | Persistence on |
| --- | ---: | ---: |
| Complete task, including two boots | 359.9 s | 244.7 s |
| First token after restart | 144.8 s | 9.8 s |
| Newly processed prompt tokens | 243349 | 121842 |
| Prefix-token reuse over all turns | 50.33% | 75.11% |
| Generated tokens, thinking included | 1766 | 1545 |
| New tokens / native prefill second | 840.2 | 824.7 |
| Generated tokens / native decode second | 62.3 | 60.6 |

This one task finished 32% sooner. The enabled run also generated 221 fewer tokens, so total wall savings are not a pure causal estimate of caching. The post-restart input was identical (121851 tokens); persistence avoided rereading 121509 of them. Decode was slightly slower. This single task does not establish general coding quality. Transcripts, tools, code and test results are retained.

## Other benchmark results

### Usual Pi agent suite

One suite per arm, thinking enabled, temperature zero/seed 42, 131072 context capacity and natural task histories (no padding). The scored histories reached 13.6K/14.1K tokens. Every native output/input/cache count matched its Pi assistant usage record. Both arms had zero API errors and zero fixture violations.

| Metric | Persistence off | Persistence on |
| --- | ---: | ---: |
| Scored task passes | 10/10 | 10/10 |
| Ten scored tasks, wall seconds | 626 | 527 |
| All eleven tasks, wall seconds | 763 | 940 |
| Scored generated tokens | 26,404 | 21,529 |
| Scored new-token prefill, tok/s | 356.6 | 362.0 |
| Scored decode, tok/s | 60.48 | 60.57 |
| Prefix-token reuse, % | 87.65 | 86.79 |
| Expert-pool resident hit rate, % | 81.34 | 79.72 |
| Direct PCIe share of all routed experts, % | 5.70 | 6.16 |

The task-balanced geometric decode ratio was 1.0012×: essentially unchanged. The lower ten-task wall time follows fewer output tokens/tool calls; it is not evidence of a cache speedup. Prefix and expert hit percentages also reflect differing trajectories, not a controlled change in their algorithms.

Task8 already passed before model edits and is excluded from the ten-task quality score, as in the previous harness. Its runtime remains visible: 137 seconds off versus 413 on. Across all eleven tasks, output rose from 32533 to 37911 tokens. Native decode time increased 106.7 seconds and prefill 4.3 seconds. The cache performed twelve synchronous saves totaling 62.4 seconds and **zero SSD restores**; RAM won on continuation hits. These account for nearly all of the 177-second whole-suite increase. This run demonstrates the write cost during continuous coding, not faster ordinary coding. All raw tasks, including task8, are retained.

### Usual speed suite

Three repeats per prompt size, same engine/config apart from persistence. No failed or skipped requests. Prompt rates below are medians; chat decode is total generated tokens divided by native decode time. These probes do not grade answer correctness.

| Probe | Off, tok/s | On, tok/s |
| --- | ---: | ---: |
| 4K prefill | 666.9 | 654.6 |
| 16K prefill | 881.9 | 867.2 |
| 32K prefill | 884.4 | 881.1 |
| Short chat decode | 57.5 | 56.0 |

Caching changes reuse and wall time; it does not modify prefill/decode kernels. The full request timings and cache-probe results are in `final-metrics.json` and the two `speed-*` result directories.

### Host-memory allocation

Exploratory one-process run per profile, after the paired campaign. Same 121K branches and checkpoints, then two independent short conversations below the 8K persistence threshold. This separates long-history recovery from native parking of small chats. No cold-SSD restart repeat is included in this allocation sweep. Five-second memory samples can miss shorter peaks.

| Native parked RAM / hot pages | Long A return, seconds | Short A return, seconds | Short reused tokens | Peak RSS, GiB | Peak swap, GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| ram4-hot1 | 6.168 | 0.385 | 5106 | 48.13 | 0.06 |
| ram0-hot4 | 3.277 | 8.789 | 0 | 48.01 | 0.01 |
| ram2-hot4 | 4.311 | 0.360 | 5106 | 48.19 | 0.02 |

`ram4-hot1` means 4096 MiB native parked conversations / 1024 MiB shared hot pages; `ram0-hot4` means 0 / 4096; `ram2-hot4` means 2048 / 4096. Each native pool has one slot. All other tested settings, including the 1024-token save gain, are unchanged. Per-request results and native page-hit bytes are in `summary.json`; actual engine budgets are recorded in `*-engine-info.json`.

## Implementation, inspiration and limits

The native server transparently selects saved prefixes using exact token/checkpoint metadata, checking native RAM first. It restores only when SSD offers a deeper reusable prefix. Native serialization writes immutable shared pages up to 2 MiB, with bounded hot RAM and SSD tiers. Atomic publication, checksums, locks, a namespace lease, unique-page quotas and LRU garbage collection preserve state. Native model/config/state validation remains authoritative.

Inspired by [oMLX at 6b413c9](https://github.com/jundot/omlx/tree/6b413c900352db1382466cf4b7f0825f61a550a9), especially `paged_ssd_cache.py`, `prefix_cache.py` and `boundary_snapshot_store.py`. No MLX code was copied. This is serialized host/SSD state paging, **not** a new GPU KV allocator or a complete oMLX port. Save/restore remains synchronous; oMLX's background writer has not been ported. A changed history reuses only an unchanged coherent checkpoint; its affected suffix must be recomputed. Retention is bounded; old executable/config namespaces need explicit cleanup after upgrades.

Linux/POSIX, one serial engine and text persistence are covered. Vision bypasses persistence. GPU KV deduplication, compression, parallel/split engines, Windows and HIP/SYCL execution were not validated. The feature stays opt-in.

## Validation and reproduction

- 264 native conversation-file checks passed: legacy golden bytes, round trips, shared prefixes, corruption/missing/linked pages, wrong model, atomic failures and hot-cache eviction. Native conversation-memory and save-reclaim suites also passed (`cpu-ctest.log`).
- Final Python code: **127 tests run, 126 passed, one optional JSON-schema check skipped** because `jsonschema` was unavailable (`python-tests-final.log`). Covers prefix indexing, normal EOS, cancellation, RAM preference, steering isolation, filesystem failures and transient memory refusal, plus existing server suites.
- Three real saved model sessions round-tripped byte-for-byte offline: 6.25 GB logical state used 4.18 GB pages plus manifests (`real-session-check.jsonl`). This is not inference latency evidence.
- A synthetic 128-history/120K-token index probe matched linear lookup results (`index-bench.json`). It measures metadata only, not model speed.

Configuration and architecture (`private/source/docs/PERSISTENT_PREFIX_PAGES.md`). Pins/build commands: `provenance.json`, `candidate-build.json`. Feature delta from preserved production tuning: `cache.patch`; previous tuning: `production-base.patch`.

GPU harnesses: `smoke.py`, `long_bench.py`, `long_agent.py`, `agent_bench.py`, `speed_bench.py`, `memory_bench.py`. Run sequentially with exclusive GPU ownership; they stop/restore the standing service and verify protected hashes. They depend on existing repository fixtures/helpers and this machine's model paths. `analyze.py` and `final_metrics.py` summarize saved evidence. Prefix-token hits, expert residency, direct PCIe routes and serialized-page hits are separate metrics; page hits include repeated identical pages within one read.

## Final state and opt-in profile

Production is restored with the original binary/config/expert-profile hashes, 131072 context capacity, vision enabled and API authentication enabled (`production-health-final.json`, `protected-check.json`). The feature remains on its separate branch: synchronous writes cost time in fresh/continuous sessions, while restart and evicted-history recovery benefit. No general decode speedup is claimed.

The preferred local **experimental** allocation is 2048 MiB native parked RAM / one slot plus 4096 MiB shared hot pages. It returned the 121K branch in 4.31 seconds and the 5113-token short conversation in 0.36 seconds, with 5106 short tokens reused. Serialized hot-page hits were 71.7%; peak sampled RSS was 48.2 GiB and process swap 16 MiB. This is one allocation run, not a repeated performance guarantee. The full ordinary agent suite and cold-SSD restart pairs used the initial allocation, not this later profile.

`candidate-text.config.json` preserves those tested knobs, with separate runtime log/profile/cache paths. It serves the tested text-only endpoint at `127.0.0.1:8087`. After stopping `strata-serve`, `./run-candidate.sh` starts this branch's server; the launcher refuses to share the GPU with an existing compute process. Stop the candidate and restart `strata-serve` to return to normal production. The candidate is not enabled automatically.

The source branch includes a compact benchmark record under `bench/results/2026-10-30-persistent-prefix-pages`. The full evidence and harness remain in this experiment directory.
