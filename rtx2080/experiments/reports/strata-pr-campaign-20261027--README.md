> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata PR campaign — 2026-10-27

Status: **stopped at the user's request**, 2026-10-27 09:12 UTC. All experiment processes were stopped; normal Strata serving is healthy and loaded at 131,072-token capacity and 165 W. The production binary, configuration and expert-profile hashes are unchanged. See `stopped.json`. Raw observations are in `results.jsonl`. No candidate has been promoted.

The grammar candidate built, but its Python server suite was interrupted before completion; its GPU parity, long JSON/tool benchmark and speed suite have not run. The combined lookup + checkpoint-reuse source is prepared but unbuilt. Novel-code and full agent validation remain unrun. Resume from these explicit boundaries; do not replay `continue_campaign.py` from its beginning, since completed phases intentionally refuse to overwrite their results.

RTX 2080 8 GiB (SM75), i5-9600K, 64 GB RAM, 165 W. Model: Swift 1.5 Qwen3.8 Flash Next GSQ-RCO IQ2_XS. The frozen custom configuration has 131,072-token capacity, 32,768 resident KV tokens, MTP 4, and the existing Turing fusion and prefill loans. Exact configuration and protected-file hashes are recorded beside this report. CPU vision remains configured. Each GPU phase runs alone and restores normal Strata serving afterward.

## Ordered experiments

1. PR4040: `--lookup-max-t 16 --lookup-sizes 8,16`, preserving MTP 4.
2. PR1536 + PR3971: generated-reply token reuse and safe thinking-budget overrun reuse, separately opt-in in the adapted server.
3. PR4039: hyper-connection scratch sharing, then larger chunks; grouped scratch is tested with fusion disabled because the upstream path requires all-MMQ layers.
4. PR3945 and PR4224 independently: checkpoint-buffer reuse and immutable parked-cache block deduplication. Each phase seeds its long prompt once, saving all prefix checkpoints (`STRATA_SESSION_ALL_CHECKPOINTS=1` only during fixture creation), restores the same seed in every arm, and switches COPPER/BRASS/IRON branches twice. Measured arms retain the normal configuration's save flag. These are warm branch-cache comparisons, not cold-prefill benchmarks. Dedup uses four slots in both arms to expose capacity benefits otherwise masked by the normal two-slot cap.
5. PR3800/PR4222: constrained JSON and tool calls with MTP, followed by ordinary chat/prefill regression checks. Baseline JSON and tool fixtures are saved with all prefix checkpoints and restored identically for every arm; these are warm long-context tests. All tool cases declare the same three-tool inventory (`read_file`, `read`, `exec_read`) and request one exact tool and argument, including overlapping tool names. Actual cached/read token counts are retained; changing the requested tool may rewind to an earlier periodic checkpoint.

PR diffs, adapted patches, pinned source metadata, build receipts, and logs are retained. Private checkouts and binaries are isolated from the normal engine. This is an evaluation of adaptations on the frozen custom baseline, not a comparison of arbitrary upstream branch heads.

## Completed: lookup

Four existing CUDA policy/parity suites passed. The patched binary with the feature disabled also passed the long edit control.

Repeated ABBA cold full-file editing: every request had 122,451 input tokens and 1,433 generated tokens. All four returned the expected Python AST, changing every integer literal 1024 to 2048 and preserving the remaining statements.

- Baseline mean wall time: 168.432 s; aggregate generation: 58.49 tok/s.
- Lookup mean wall time: 165.645 s; aggregate generation: 66.64 tok/s.
- Generation gain: 13.94%; total request reduction: 1.65%. Prefill was essentially unchanged (851.8 vs 850.5 tok/s).

The usual speed suite completed without failures/skips: short-chat median 44.3 → 44.7 tok/s, conversation generation 42.2 → 43.7 tok/s, 32K fresh prefill 884.5 → 884.5 tok/s. These small general-workload differences come from one suite per arm and are not established speedups. The edit result is not evidence of a 14% end-to-end agent gain.

Novel-code generation at roughly 122K context and a full agent comparison remain pending. Earlier lookup settings had regressed novel-code generation, so the edit-only gain is insufficient for promotion.

## Completed: reply and budget reuse

The adapted Python server passed 36 focused encoder/budget tests. Four long-context sequences ran in ABBA order from the same saved seed; all four full-file AST and follow-up recall checks passed.

No improvement was observed: the ordinary follow-up read 38 new tokens in both arms and averaged 0.966 s baseline versus 0.976 s patched. Budgeted requests averaged 170.03 s versus 170.53 s, including the shared cold reread caused by switching reasoning mode. Each wrap read 19 tokens, and neither patched request collected extra in-flight tokens. This fixture did not reproduce the overrun failure that PR3971 targets; passing it does not establish that the patch is unnecessary in every workload. No promotion on this evidence.

## Scratch screen and repeated long edits

All four cold 122,451-token edit screens passed the exact AST check:

- Baseline 4,096 chunk: 166.07 s, prefill 862.5 tok/s.
- HC scratch sharing, 4,096 chunk: 167.26 s, prefill 857.1 tok/s.
- HC scratch sharing, requested 6,144 chunk: 179.68 s, prefill 792.1 tok/s. The engine reduced the actual chunk to 3,072 because 6,144 did not fit.
- HC + grouped scratch, fusion disabled, automatic chunk: 179.95 s, prefill 789.3 tok/s. The actual chunk was 4,608.

The larger chunks did not improve this already-fused custom configuration. The closest variant, HC sharing at 4,096, completed ABBA repeats with all files correct: baseline mean 168.266 s versus candidate 167.785 s (0.29% shorter). This is effectively parity, not a meaningful speedup. Both ordinary speed suites passed: 32K prefill 883.0 → 887.5 tok/s, short chat 43.8 → 46.1 tok/s, conversation generation 41.0 → 44.3 tok/s. Prefill differences are tiny; chat/decode differences are from one suite per arm with varying replies and are not established repeatable gains. No promotion on this evidence. Do not interpret the upstream author's gain over a different baseline as a measured gain here.

## Completed: checkpoint-buffer reuse

PR3945 built successfully and passed all seven selected cache/snapshot tests, including the CUDA snapshot test, with no skips. All 24 branch retrievals in the ABBA benchmark returned both document sentinels and the correct branch marker.

For the six cached revisits per setting, mean wall time fell from 1.9673 s to 1.8167 s: **7.65% lower latency, 150.6 ms saved per revisit**. Both enabled runs showed the direction of improvement. New-branch requests were unchanged (49.644 vs 49.626 s), reading 39,096 tokens after reusing 81,920. Each cached revisit reused 121,009 tokens and read seven. The diagnostic confirms six checkpoint buffers totaling 676 MiB moved rather than copied during the relevant parks. This is a branch-switch latency benefit, not a decode or cold-prefill speedup. It is a candidate for combined validation.

## Completed: parked-cache deduplication

PR4224 passed nine cache/storage tests and all 24 long-context branch checks. Revisit latency averaged 2.0939 s disabled versus 1.8386 s enabled (12.2% lower); new-branch processing remained essentially unchanged (49.697 vs 49.529 s). These use the same binary off/on and four configured slots; the observed parked-entry count was two. The change is a separate candidate, not stacked with PR3945: both alter checkpoint ownership/admission, and their patches conflict in those paths.

Both enabled repeats reported identical final storage ledgers: 7,904,177,088 logical payload bytes and 4,264,948,096 physical payload bytes, a 46.0% internal payload saving (3,639,228,992 bytes). This includes live snapshot references, active checkpoints and temporary state; it is **not** an off/on process-RSS measurement. Metadata was separately bounded at 6,301,828 bytes. The smaller PR3945 remains the initial latency-focused combined candidate; dedup is retained separately as the memory-saving option. Its absolute revisit latency was similar to PR3945's, so the two relative percentages must not be added.

## Interpretation rules

Capacity is 128K throughout, but actual prompt sizes are reported per test. Focused long tests use roughly 121K–124K tokens; the standard suite uses short chat and 4K/16K/32K prompts. Agent runs use their natural contexts and must not be described as 122K runs unless their recorded requests reach that size.

Throughput, first-token time, total request time, generated-token counts, and correctness are evaluated separately. A saved-prefix test measures warm continuation, not cold prefill. The reuse fixture switches from no reasoning to high reasoning for its budget test; that template change triggers a cold reread in both arms and must be distinguished from reuse within the thinking wrap. Its 1,024-token cap can truncate the final answer; nonempty final text is a functional check, not a complete code-review quality pass.
