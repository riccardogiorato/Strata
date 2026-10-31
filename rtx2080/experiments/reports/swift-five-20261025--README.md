> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Swift: five optimization tracks, 2026-10-25

Status: **all five tracks complete**. Results below are local measurements, not claims about other GPUs.

The useful changes are bounded extra prefill loans (204 to 150 seconds first token at 121K), automatic SSD session resume (151 seconds cold to roughly 4–5 seconds including restore), and explicit document-boundary pinning (about 13 to 0.75 seconds for replacement questions). The alternative CPU kernel and sustained decode settings did not show a useful gain. PCIe retention showed a tentative +4.2% on an older patched binary, insufficient to justify replacing the current engine. A tested optional text-only profile and SSD-backed launcher are included below; the standing service was not changed.

Model: Swift 1.5 Flash-Next GSQ RCO IQ2_XS, two GGUF shards. Hardware: RTX 2080 8 GB and i5-9600K. Tests run serially at 165 W with a 131072-token context allocation. The frozen coding archive contains 121006 input tokens and two retrieval sentinels; sustained generation requests allow 2048 output tokens. Thinking is disabled. Test servers bind localhost:8087. Each phase restores the original Bolt container and 225 W power limit.

`results.jsonl` contains request-level measurements and correctness checks. Configs and engine logs are retained per arm. `long-code.json` freezes the workload. Short executable code checks are smoke tests, not an agentic-quality benchmark; 2048-token outputs are deliberately truncated and are not scored as complete queue implementations.

## 1. Extra borrowing and PCIe retention

Ordinary expert-cache borrowing was already enabled. This tests additional prefill loans from the MTP/head allocations and repeat borrowing.

| ABBA arm | First token, seconds | Prefill tok/s | Decode tok/s | Total seconds |
|---|---:|---:|---:|---:|
| Original baseline 1 | 203.46 | 595.4 | 52.2 | 242.65 |
| Bounded loans 2 | 149.22 | 812.1 | 52.2 | 188.39 |
| Bounded loans 3 | 150.99 | 802.5 | 54.1 | 188.80 |
| Original baseline 4 | 204.89 | 591.2 | 51.6 | 244.52 |

Mean first-token latency falls 26.5%, total request time falls 22.6%; mean prefill throughput rises 36.1%. All four retrieval and four executable-code checks pass. This is a **configuration bundle** comparison: loan flags plus `--prefill 4096 --expert-cache 2000`, not an isolated estimate of each flag. Short prompts can pay more memory-management overhead.

Unbounded loans failed at startup (`cublasCreate`, status 1). A `--prefill auto:4096` attempt did not cap at 4096: the parser rounds automatic maxima to a larger supported bucket. Explicit 4096 alone still exhausted startup headroom. Limiting the expert cache to 2000 requested slots fixed startup; actual mixed-size allocation was 2083 slots / 2.81 GiB, and prefill borrowed 1898 slots / 2.56 GiB. Decode resized the cache when deferred weights loaded.

PCIe retention is a separate matched ABBA test on the retained experimental `prcombined-strata` binary. Its `STRATA_ADAPT_FETCH` patch is absent from the current 0.2.3 and 0.2.6 sources. A result on that binary is not evidence that setting the flag on today's binary works. The completed ABBA measured off 54.7 / 51.7 and on 54.5 / 56.4 tok/s: means 53.20 and 55.45 (+4.2%). Mean request wall time fell 40.06 to 38.90 seconds (-2.9%). All four code checks passed and the admission gate was active. Individual ranges overlap and the first on run did not beat the first off run, so this is tentative evidence, not a robust large gain. Do not replace the current binary or assume the gain adds to other optimizations.

## 2. SSD session persistence

`session_cache.py` implements a local serial OpenAI chat proxy around Strata's native session save/restore API. It adds automatic snapshots, restart discovery, explicit `X-Session-ID` support, an engine/model identity namespace, and LRU eviction. It retains actual recurrent/KV/draft state, not merely chat text. Clients must still send their complete history. Prefix validation remains the engine's responsibility.

The ten unit/integration tests cover restart restore, identity isolation, quota eviction, failed requests, save thresholds, safe filenames, restore failure, HTTP SSE forwarding, and replacement of missing/failed snapshots without token growth. Live GPU validation passed across two fresh engine restarts: 120977 tokens reused, correct retrieval answers, 4.06 and 4.86 seconds including restore versus 151.19 seconds cold. The 2.08 GB snapshot took 2.15 seconds to save and 1.84–2.08 seconds to restore. These timings exclude model startup in both cases. An additional real HTTP-proxy request evicted only the snapshot from the OS file cache and verified zero resident pages with `fincore`; it restored and answered correctly in 3.60 seconds with 120977 tokens reused. This validates the disk-read path, although it is not a full machine reboot test.

Experimental scope: `/v1/chat/completions` only, localhost binding, one upstream slot, one proxy process per cache directory. Restart the proxy together with the upstream. Use a distinct private directory for each model/engine configuration; the quota covers the indexed snapshots for that identity. Snapshot saves add time after generation. Files can contain private prompt state; the directory is private and no cache data should be committed.

## 3. Checkpoint placement

Matched default/spread ABBA tests modify the frozen history at 40% of its character length, then check both retrieval sentinels. A separate default/pinned-prefix comparison replaces the final question twice. This distinguishes SSD persistence across restarts from ordinary RAM checkpoint reuse within a live process. The completed default/spread ABBA found no useful difference: both reused 16384 tokens, with mean request times 133.81 and 133.43 seconds. All four edited-history retrieval checks passed. This does not establish that spread is ineffective at other edit positions.

Explicit document-boundary pinning **did** help in the paired screen: two changed questions took 12.39 / 13.51 seconds by default and 0.85 / 0.65 seconds pinned. Reused tokens increased from 114688 to 120955; all four answers passed. The first document read remained about 152 seconds. The request used `strata_prefix={"message":1,"chars":len(document)}` with a system message at index 0 and the document plus question in user message 1. Use the actual stable boundary in your own request. This result covers a live engine; native disk snapshots retain only the deepest checkpoint, so do not assume a separate pinned document checkpoint survives a restart. SSD resume and pinned-question gains are not additive.

## 4. Profile and targeted kernel

`profile.py` enables native decode timing and verifier profiling. Profiling results are diagnostic, not speed baselines. The tested candidate was the existing AVX2 exact single-token IQ expert kernel, gated by `STRATA_CPU_IQ_ALL_EXACT1=1`; the measured CPU contribution supports testing it: 18.91 ms/window in CPU expert work versus 1.00 ms/window in QSA score/top-k. Total window time was 46.95 ms, verification 42.98 ms, GPU-reach wait 21.06 ms and drafting 2.97 ms. These timings overlap; do not sum CPU and GPU counters as disjoint work. No TensorFold kernel has been ported.

The AVX2 ABBA completed with the gate confirmed active in both candidate logs. Baseline decode was 56.1 / 53.8 tok/s; exact1 was 56.8 / 53.2 tok/s. Means: 54.95 versus 55.00 tok/s; mean request wall time 38.98 versus 39.06 seconds. All four code checks passed. **No useful gain; leave this flag off.** Long generated outputs varied even between repeated baseline runs, so these are practical request measurements, not a bitwise kernel-parity proof.

## 5. Sustained drafting and overlap

A separate latest-Strata 0.2.6 screen compares synchronous adaptation, automatic async selection, forced async, transfer overlap, and MTP widths 2 and 6 against default width 4. Each arm generates up to 4096 tokens over two turns at 121K+ context, followed by executable-code validation. The latest engine lacks our older prefill-loan patch, so its results must be compared within this screen. The completed screen produced:

| Mode | Combined decode tok/s | Output tokens | Change versus baseline |
|---|---:|---:|---:|
| Synchronous MTP-4 baseline | 54.55 | 4096 | — |
| Automatic adaptation | 54.30 | 4096 | -0.5% |
| Forced async (`--adapt-async 1`) | 53.07 | 4096 | -2.7% |
| Transfer overlap | 54.88 | 4096 | +0.6% |
| MTP-2 | 48.53 | 4096 | -11.0% |
| MTP-6 | 47.32 | 3773 | -13.3% |

Combined rates are total generated tokens divided by total engine generation time across both turns. MTP-6 stopped naturally before the continuation limit. All six executable-code checks passed. Automatic mode remained blocking; forced async and transfer overlap were confirmed active in their logs. Overlap's 0.6% difference is below the observed run variation, so no candidate was promoted or taken to an additional winner/control repeat. Keep MTP-4 with the existing adaptation policy.

Request wall time also depends on prefix reuse: the baseline continuation reread 2087 tokens, while several other arms reread only 40. That is why lower request wall time alone is not evidence of faster decode here. Generated text differs across runs, including repeated baselines.

Flag correction: `STRATA_ADAPT_ASYNC=1` allows automatic choice in 0.2.6; it does not force async. The initial forced-arm setup was interrupted before its measured request, then resumed with explicit `--adapt-async 1`. Completed baseline/automatic results were retained; no unforced result is labeled as a forced-async measurement.

The retention, kernel, and sustained-decode phases use a common disk seed per engine binary: the exact 121006-token coding request with one generated token. Each arm starts a fresh process, restores the same seed, and must report more than 100K reused tokens. This holds the long context constant while avoiding redundant cold prefill; decode throughput is the comparison metric. The separate borrowing experiment above still measures full cold prefill. Original cold-only draft scripts are retained as `*-cold-design.py` and were not run.

## Reproduction

Run one phase at a time from the repository root:

```bash
python3 experiments/swift-five-20261025/profile.py
python3 experiments/swift-five-20261025/retention.py
python3 experiments/swift-five-20261025/cache_bench.py
python3 experiments/swift-five-20261025/kernel.py
python3 experiments/swift-five-20261025/sustained.py
python3 -m unittest discover -s experiments/swift-five-20261025 -p test_session_cache.py
python3 experiments/swift-five-20261025/quick_summary.py
```

The scripts use local engine/model paths from the standing configuration. They stop Bolt during each phase and restore it in a `finally` block. Do not run alongside other GPU work. `borrowing.py` is the bounded retry sequence; the original first baseline and failed initial scripts are retained separately.

## Optional local SSD-backed launcher

`longcontext-candidate.json` is the validated text-only borrowing candidate. It does not replace the standing service config. Once other GPU inference is stopped, launch both processes together from the repository root:

```bash
python3 experiments/swift-five-20261025/launch_cached.py \
  --config experiments/swift-five-20261025/longcontext-candidate.json \
  --cache-dir "$HOME/.cache/strata-ssd-sessions" \
  --engine-dir ../strata-023 \
  --python ../strata-023/.venv314/bin/python
```

Use `http://127.0.0.1:8088/v1/chat/completions`, send the full message history, and set a stable `X-Session-ID` per conversation. Ctrl+C stops both processes. This is a local chat proxy, not a replacement for Strata's other APIs. The launcher does not stop another inference server or change the GPU power limit. Its live smoke test passed: proxy health and completion succeeded, and Ctrl+C stopped both processes with no remaining GPU inference process.

## Completion and limits

67 measured API requests completed. All 33 explicit live retrieval/code/proxy/lifecycle checks, three disk-roundtrip checks, and ten cache unit/integration tests passed. These are focused smoke checks, not a rerun of the full agentic-quality leaderboard. The long queue implementations are not graded as complete programs.

`final-state.json` verifies Bolt is running and healthy, the GPU is back at 225 W, and the previously inactive Strata service remains inactive. Hashes of the standing Strata config, expert profile, and service unit are unchanged. No commit, push, or production-service replacement was made. `summary.json`, `sustained-scores.json`, `provenance.json`, and per-arm logs provide the evidence. Large private snapshots live in the git-ignored `ssd-cache/` directory.
