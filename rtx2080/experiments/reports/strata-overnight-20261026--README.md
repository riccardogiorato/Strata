> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata optimization results — 2026-10-26

Completed and validated locally. The useful gains are in long-context conversation reuse; no reliable increase in raw generation speed was found. The optimized executable and two launch profiles are ready. The original installed executable and normal GPU setup were restored.

A follow-up compute campaign (`../strata-compute-20261026/README.md`) subsequently measured 10.3% higher cold-prefill throughput using native Turing fusion. Its profiles combine that change with these cache features.

## Measured results

RTX 2080 8 GB, i5-9600K, 64 GB RAM; Swift 1.5 Flash-Next GSQ-RCO IQ2_XS. Context capacity 131,072, with approximately 121,000–122,500 input tokens. Modified Strata 0.2.3 / native engine 0.1.48, including the existing Turing and prefill-loan patches. Tests ran at 165 W. Model startup (16–22 seconds) is excluded from request timings.

| Test | Baseline | Candidate | Result |
|---|---:|---:|---|
| Resume an older saved branch after restart, ABBA means | 35.44 s | 5.23 s | 6.77× faster request; same answer |
| Promote restored host state into native RAM cache, ABBA means | 5.50 s | 4.58 s | 16.6% less waiting |
| Final everyday launcher, restart with cold file cache | — | 4.44 s | Correct answer; 120,988 tokens reused |
| Edit earlier history after restart, request only | 151.37 s | 100.96 s | 33% less request time; 40,960 tokens reused |
| New-code generation, repeated ABBA | 57.37 tok/s | 52.44 tok/s with lookup 8 | Keep original lookup default |

The branch comparison uses the same patched binary and full snapshots in both arms: latest-only selection versus selecting the matching saved branch. It is a restart/SSD test, not proof of faster switching between already-hot RAM branches. The indexed cold-file-cache result was 5.36 seconds. `fsync`, `posix_fadvise(DONTNEED)` and `fincore` verified zero resident snapshot pages before cold-file tests.

The history edit inserts text at 40% of document **characters**, not tokens. Original snapshot restore took another 1.86 seconds; the final dense profile restore took 3.56 seconds, for 104.52 seconds total. This is a focused single edit scenario, not an ABBA result. Earlier screens with six saved checkpoints and fifteen saved checkpoints took 133.65 and 104.28 seconds respectively, excluding restore. Cold prefill remained about 149–152 seconds: no new cold-prefill gain is claimed.

These gains must not be multiplied together: they overlap and use different comparisons.

## Implemented

- **Branch-aware SSD index:** hashed request prefixes select a matching native snapshot, including histories changed without growing in length. Native Strata still validates actual token prefixes and model identity before reuse.
- **Save throttling and bounded eviction:** appended turns defer another snapshot until 1,024 tokens of progress. Changed histories can save distinct branches. Default minimum save is 8,192 tokens, with a 16 GiB LRU quota per configuration/executable identity.
- **Native checkpoint-chain persistence:** optional `STRATA_SESSION_ALL_CHECKPOINTS=1` saves every currently retained checkpoint, with RAM admission before copying. The dense profile retains up to 16 checkpoints, spaced 8,192 tokens apart, to recover more work after earlier edits.
- **Native disk-to-RAM promotion:** `STRATA_SESSION_RESTORE_HOT=1` moves the already-read large host KV allocations into the conversation cache instead of discarding them and copying GPU state back again. Mutable metadata is copied independently; memory and cache admission gates apply.
- **Agent API proxy:** Chat Completions, Responses, Anthropic Messages and Anthropic token counting; native tool payloads, streaming and non-streaming supported.
- **Optional message-boundary pinning:** `--auto-pin` selects a complete large text message before the final message for Chat Completions. Explicit `strata_prefix` takes precedence.
- **Packaged launcher:** starts native engine and proxy, isolates caches by executable/configuration identity, locks ownership, checks GPU availability and shuts down both processes cleanly. Immediate restart was tested after fixing socket preflight handling of `TIME_WAIT`.
- **Q4 draft-head guard:** the old conversion path assumed Q4 always shrinks the native head. Our head measured 1,360 bytes per row versus 1,440 for Q4_0. Conversion now safely skips this no-benefit case. The real GPU regression and executable-code check passed; Q4 is not enabled in the selected profiles.

Existing Strata already saves the deepest pinned checkpoint, otherwise the deepest checkpoint. The checkpoint state survives save/restore; its runtime `pinned` flag is not serialized. Explicit pinning should be supplied on the next request. This corrects the earlier claim that pinned checkpoint state was not saved.

## Selected profiles

**Everyday coding/chat:** `cached-profile.json`, using `strata-optimized`, hot promotion, small native snapshots and the existing MTP 4/default suffix lookup. Small and full snapshots had effectively identical resume means (4.47 versus 4.46 seconds). The small snapshot was 2.085 GB and saved in 1.51 seconds, versus 2.676 GB and 3.30 seconds for six checkpoints.

**Frequent earlier-history edits:** `history-edit-profile.json`, adding dense full-chain persistence. The measured fifteen-checkpoint snapshot was 3.741 GB and took 5.28 seconds to save. This trades disk space and save cost for more reusable boundaries.

From the repository root, with the other GPU server stopped:

```bash
python3 experiments/strata-overnight-20261026/launch_cached.py \
  --config experiments/strata-overnight-20261026/cached-profile.json \
  --cache-dir "$HOME/.cache/strata-ssd-sessions" \
  --engine-dir ../strata-023 \
  --python ../strata-023/.venv314/bin/python \
  --auto-pin
```

OpenAI-compatible base URL: `http://127.0.0.1:8088/v1`. Anthropic base URL: `http://127.0.0.1:8088`. Send a stable `X-Session-ID`, especially when editing the first user message. Use the history-edit configuration instead for dense persistence. Ctrl+C stops both processes. These local profiles contain machine-specific model paths. The proxy imports the existing `experiments/swift-five-20261025/session_cache.py` module.

## Validation and rejected candidates

- 205 native conversation-file checks and 119 reclaim checks passed. Dedicated hot-restore ownership, metadata independence and admission-refusal checks passed.
- 13 branch-cache tests, 10 existing session-cache tests and 3 API tests passed. API tests cover six protocol/streaming combinations and token counting.
- All 56 recorded live correctness checks passed, including retrieval, executable code, full-file AST comparison, real structured tool calls and packaged launcher lifecycle. Experimental failures remain in the logs; they are not silently counted as passing.
- Anthropic long-context cold request: 153.75 seconds; restart: 5.15 seconds. Responses: 153.89 seconds; restart: approximately 5.20 seconds. Correct retrieval and structured `read_file` calls were verified across all three inference protocols.
- Cost-aware speculation and lookup-chain depth 2 did not establish a gain. Lookup 8 looked promising in the initial screen but lost in repeated new-code tests. Full-file edit ABBA also favored the original default: 59.03 versus 57.01 tok/s, with all four AST checks passing. Defaults were retained.
- The Q4 head screen initially failed, motivating the guard above. The corrected path passed its real GPU regression.

## Scope and limits

This is whole-session snapshot persistence and indexing, **not** oMLX-style shared block caching. Snapshots duplicate shared KV bytes; quota eviction removes older branches. Editing a prefix invalidates its dependent suffix. RAM caching remains native Strata behavior. The proxy does not inspect native parked-branch inventory, so it can conservatively restore an SSD snapshot even when that branch is already in RAM. Warm branch switching needs separate measurement.

Inference through this proxy is serial. Native Responses requires full history on each request. This is a text-only campaign with focused checks, not a full vision or agentic leaderboard rerun. Previous VRAM borrowing and prefill-loan settings are carried forward, not counted as new optimizations. No claim of 2×–1,000× general decode improvement is supported.

## Sources, reproducibility and rollback

See IDEAS.md (`IDEAS.md`) for the primary-source audit of Rapid-MLX, oMLX, SGLang and LMCache. Rapid-MLX was inspected at commit `a9593a7bbd2c4b4c18afad1ea054af0d55dbd23e`; our own cache implementation was written, and no Apple Metal kernels were copied into CUDA.

`native-speedups.patch` contains the native changes against the existing modified local checkout. `checkpoint-chain.patch` is the earlier checkpoint-only delta. `source-before/` retains original files locally. `provenance.json` records source, executable and patch hashes. `results.jsonl`, response files and engine logs preserve measurements; `summary.json` is generated by `summarize.py`.

Synthetic benchmark SSD snapshots are removed after validation, with their sizes recorded in `cleanup-manifest.json`. Scripts can recreate them in campaign order. Binaries and rollback source backups remain locally and are ignored by Git. No commit or push was made. `final-state.json` records restoration checks.
