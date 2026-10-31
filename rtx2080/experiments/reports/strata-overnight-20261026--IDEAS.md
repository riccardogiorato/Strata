> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Engine ideas audit, 2026-10-26

Rapid-MLX inspected commit a9593a7bbd2c4b4c18afad1ea054af0d55dbd23e:
https://github.com/raullenchai/Rapid-MLX

- `rapid_mlx/prefix_cache.py`: prefix indexing, bounded eviction, hybrid snapshot safety. Implement our own hashed-prefix branch index over native Strata session files. This is whole-session persistence, NOT block-level paged tiering.
- `rapid_mlx/spec_decode/mtp/draft_k_controller_v2.py`: expected committed tokens / measured cost, smoothing outliers, probing depths. This module itself credits Ollama. Strata already has `DraftPolicy`, measured context-specific cost tables and optional `STRATA_SPEC_COST`; test that existing option before adding a duplicate controller.
- `rapid_mlx/spec_decode/mtp/prompt_lookup.py`: repeats from prompt as draft proposals. Strata already has suffix drafts (default 3) and optional `--lookup-chain`. Test the latter on long-context coding.
- Rapid Metal kernels cannot run on Turing CUDA. No portable performance claim from Apple silicon benchmarks.
- Existing Strata features already cover graphs, quantized KV, MTP, prompt lookup, expert VRAM borrowing. Do not call enabling them a new kernel implementation.

SGLang HiCache: https://www.sglang.io/blog/hicache
Retaining hybrid recurrent state at several prefix/branch boundaries motivates the opt-in native checkpoint-chain persistence patch. Original Strata save prefers deepest PINNED checkpoint, otherwise deepest checkpoint. Earlier explanation that pinned checkpoints were never saved was incorrect.

oMLX: https://github.com/jundot/omlx#tiered-kv-cache-hot--cold
Persistent cold storage and bounded eviction motivate the proxy. RAM remains Strata's native conversation cache. This implementation does not promise every past context remains cached.

LMCache: https://docs.lmcache.ai/recipes/qwen3_8_flash_next.html
Hybrid state groups must be restored coherently. Keep native Strata's complete validated format; do not compress/trim recurrent state as if it were ordinary token KV.

Not pursued without further evidence: new quantization of target weights, lossy cached state, removing vocabulary entries, replaying cached answers, CUDA ports of architecture-specific Metal kernels. No new model downloads required.

Final findings: the branch index and optional checkpoint chain helped restart/history reuse. Native host-buffer promotion removed a redundant copy path, measured separately at 16.6% less wait. The default uses smaller snapshots; dense chains are reserved for history edits. Repeated decode tests rejected lookup 8, and cost/depth candidates did not establish gains. A native Q4 head size guard fixes an exposed conversion failure; it is a correctness fix, not a claimed quantization speedup. These changes are original implementations informed by the source audit, not direct ports of Metal kernels.
