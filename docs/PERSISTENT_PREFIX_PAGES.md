# Persistent prefix pages (local experiment)

A text conversation can resume after the server restarts or its native RAM conversation is evicted. The server selects a compatible saved prefix automatically for Chat Completions, Responses and Messages, using the final token IDs produced by its normal chat template. It first checks the native live/checkpoint/parked cache: RAM wins a tie.

This is an opt-in local branch based on the tested v0.2.7 configuration. It is not an upstream release feature. The native GPU KV allocator and inference kernels are unchanged.

## Enable

Use this branch's rebuilt engine **and** its Python server. Add these entries to the server config's `env` object:

```json
{
  "STRATA_SESSION_PAGED": "1",
  "STRATA_PREFIX_CACHE_DIR": "/absolute/path/to/private-ssd-cache",
  "STRATA_SESSION_PAGE_HOT_MIB": "1024",
  "STRATA_PREFIX_DISK_MIB": "24576",
  "STRATA_PREFIX_MAX_ENTRIES": "128",
  "STRATA_PREFIX_MIN_TOKENS": "8192",
  "STRATA_PREFIX_SAVE_GAIN": "1024",
  "STRATA_SESSION_ALL_CHECKPOINTS": "1"
}
```

Use `--prompt-cache 20 --prompt-cache-every 8192` for a dense checkpoint chain at a 131072-token context capacity. These checkpoint settings consume additional host RAM; use the same settings in a comparison with persistence disabled. The existing native memory floor and conversation-cache budgets still apply. The page cache is an additional bounded host allocation, not borrowed VRAM. Default page budget is 256 MiB; zero disables that tier. The experiment uses 1024 MiB. Its Linux page-cache residency is managed separately by the OS.

Start `python -m serve.server --engine strata --config /path/to/config.json` from this source checkout. Removing `STRATA_PREFIX_CACHE_DIR` disables automatic persistence; no proxy or client-specific session header is required. Existing raw session files remain readable. `STRATA_SESSION_PAGED=1` also selects paged storage for explicit native SAVE commands; use a dedicated private directory.

Cache data contains token IDs and model state derived from prompts. Keep the directory private. Each executable/config identity gets its own subdirectory, lease and quota. Old namespaces do not expire automatically across software upgrades. Stop the owning server before removing an old namespace to reclaim it.

## How it works

1. SHA-256 hashes of exact token prefixes index coherent saved checkpoint boundaries. This is an index hint; the native session reader still validates the model/config identity, complete state, checksums and dimensions before applying anything to the GPU.
2. A new `CACHEMATCH` native command reports how many input tokens the live/checkpoint/parked state can actually reuse without mutation. Only a strictly deeper disk candidate triggers RESTORE.
3. The native serializer writes immutable, content-addressed pages up to 2 MiB each. It resets page alignment at each tensor/vector, so identical leading bytes can be shared even when snapshot metadata or lengths differ. Two seeded native hashes name each page; existing bytes are compared before deduplication. These are trusted-cache integrity checks, not authentication.
4. A bounded native RAM LRU holds serialized pages. SSD is the persistent backing tier. Restore streams pages into the existing validated session parser without assembling another whole temporary file. The parser still materializes the complete validated session image before device transfer.
5. After successful generation, the server saves a snapshot if it adds enough reusable prefix. An identical request or less than the configured gain since a coherent saved checkpoint skips that write. Cancellation, vision and prefill-only requests are not persisted by this integration.
6. Quotas count unique referenced page bytes plus manifests. LRU eviction removes manifests and then only unreferenced pages. Native readers/writers and garbage collection share file locks; files and manifests publish through flushed temporary files and atomic renames. Startup collects unreachable pages and interrupted temporary writes.

The recurrent state of this hybrid model cannot be sliced at arbitrary token positions. A history edit reuses the deepest unchanged **saved checkpoint**; the changed suffix is recomputed. Retention is bounded by quotas. A RAM page hit is not a token hit: page read counters include repeated reads of the same page within one restore. Actual reusable token counts come from native RESUME/timings.

## Limits and measurement

Linux/POSIX, one serial native engine per cache namespace, text only. Parallel batching, split/peer engines and automatic vision persistence are not supported here. The feature does not deduplicate active GPU KV blocks, avoid every device-to-host save copy, compress pages, or preserve arbitrary downstream state after a history change. Save/restore remains synchronous under the existing request FIFO; cold requests can be slower because they create the cache. Native disk-space admission conservatively reserves space for a whole logical snapshot, even if sharing would save space.

Compare cold requests, native RAM hits, evicted branches, process restart and edited histories separately. Include save/restore time in wall time and TTFT; measure newly read tokens per prefill second, generated tokens per decode second and task correctness. Keep expert-residency hits separate from prefix-token hits. No production default changes are made by this branch.

Inspired by [oMLX](https://github.com/jundot/omlx/tree/6b413c900352db1382466cf4b7f0825f61a550a9), especially `omlx/cache/paged_ssd_cache.py`, `prefix_cache.py` and `boundary_snapshot_store.py`: persistent content-addressed blocks, bounded hot/cold tiers, and explicit coherent recurrent-state boundaries. This is original Strata-specific code; no MLX implementation was copied.
