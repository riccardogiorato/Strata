> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Swift IQ2_XS serving correctness checks — 2026-10-23

These are measured diagnostic checks, not a rerun of the behavioral benchmark or proof that looping is fixed. All GPU work ran sequentially with the same Swift IQ2_XS weights and existing engine. Production configuration and source were not changed by this experiment. The production service was inactive before testing.

## Cache restoration

The repository's `tools/conversation_cache_parity.py` passed its A/B/A and checkpoint gate at approximately 1,449 prompt tokens, including byte-exact main-model state and identical output. Raw evidence: `cache-int8/results.json`, the two engine logs, and `cache-int8.console.log`.

The subsequent logit probes exercised fresh prefill and restored prefixes at 1,537, 6,144, and 6,145 input tokens. Restored-prefix lengths were 1,536, 1,537, and 6,144 respectively. All three selected the same top token as fresh prefill. Distributions differed; this is not a byte-exact fresh-vs-restored result. A fourth 1,536-token replay had zero reuse and is explicitly excluded from the restore count. The `cold-*` labels inside the cache-enabled arm mean first visit to that length, not necessarily fresh prefill; use the recorded `reused` field.

## KV precision and repeat variation

Fixed transcript token prefixes from the earlier task-14 session were probed at 1,536, 1,537, 6,144, and 6,145 tokens. This fixture serializes observed transcript text into one diagnostic user input; it does not reconstruct the original HTTP conversation or tool protocol. Every arm receives identical token IDs. Each probe emits one token; neighboring probes use fixed recorded tokens rather than feeding back generated output.

| Input tokens | Repeat INT8 KL | FP16 → INT8 KL | Top token matches |
| --- | ---: | ---: | --- |
| 1,536 | 0.00000496 | 0.00002944 | Both comparisons yes |
| 1,537 | 0.00003645 | 0.00008944 | Both comparisons yes |
| 6,144 | 0.00045923 | 0.00300557 | Both comparisons yes |
| 6,145 | 0 | 0.00107408 | Both comparisons yes |

KL measures the change in next-token probability distribution; larger is more different. Precision differences exceed measured repeat variation at these points, especially at the longer input, but four selected positions are insufficient to assess aggregate quality or diagnose the earlier looping. FP16 has not been shown to fix it.

All five logit arms reported 1,062 expert slots, prefill capacity 1,280, context 8,192, and matching residency/CPU-worker settings. Adaptive swaps, suffix drafting, and route-tail skipping were disabled. CPU prefill sharing remained enabled, so fresh computations need not be bit-identical. Non-cache arms had zero reused tokens on every request. Settings are checked in `comparison-validation.json`; full runtime information is in `probe-results.json`.

## Prompt fidelity

The installed template is byte-identical to the publisher's Swift template at revision `0bd4fe22431372cdad1979267d3ab45aa7e6150a`. Source URL and hashes are in `template-source.json`.

With the experimental `plain_prompt` disabled and normal effort placement, basic and tool-roundtrip prompts matched publisher-rendered tokens at xhigh, medium, and low (6/6). The experimental plain mode matched only medium: it forcibly substitutes medium for other requested efforts. The xhigh/low reasoning instructions in this template are publisher-authored, not Strata-authored additions. This corrects the earlier interpretation of those instructions.

The empty-assistant-history fixture differs even with plain mode disabled: `ChatTemplate.render` filters empty intermediate assistant turns. This is separate from reasoning prose and was not established as a cause of the observed failures. The audit covers render-time fidelity, not HTTP adaptation, literal-token escaping, or budget-exhaustion continuation injection.

## Speculative decoding

Two greedy multi-token requests produced identical complete token arrays with drafting disabled (`--spec 2 --mtp-max-t 1`, the native-pack single-token path) and enabled (`--spec 4 --mtp-max-t 4`). Output lengths were 25 and 64 tokens. Enabled drafting accepted 19/21 and 48/48 proposed tokens, respectively, proving this exercised actual speculation. The counting request ended at its 64-token cap. This is a small parity smoke test, not a long-trajectory correctness guarantee. See `spec-decode-comparison.json`, `spec-decode-results.json`, and the engine logs.

## Scope and reproduction

`run-diagnostics.py` produced the fixed-input logits and `comparisons.json`. `audit-prompt.py` produced the prompt audit. `spec-decode.py` is the separate multi-token speculative-decoding check; its results are saved separately. Read those results rather than treating one-token logit probes as proof of draft acceptance.

Engine/source hashes and dirty checkout status are in `provenance.json`. No model weights were moved or downloaded. Diagnostic configs bypass the experimental plain mode; they do not alter the production config. This run does not test 24K–128K context, compaction summaries, task-14 functional correctness, or long agent trajectories.

All probes completed and their private engines exited. The production service remained inactive. No cache corruption was demonstrated, and neither FP16 nor disabling speculation was shown to fix the earlier behavioral failures. The prompt audit establishes that our experimental plain-mode override is not publisher-faithful outside medium effort; retaining the publisher template is the appropriate baseline for subsequent behavioral tests.
