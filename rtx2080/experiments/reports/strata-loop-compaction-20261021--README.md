> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Pi / Strata loop and compaction investigation — 2026-10-21

Source incident: T3 thread `26432f82-4529-4199-9efb-80f71a27f2c0`, “Prepare Project for Twitter Launch”.

## Findings established before the comparison

- Pi 1.3.0 recorded ten **completed** compactions in the source session. The gaps from the preceding session event total 49.15 minutes; these are elapsed intervals, not CPU time. Summarization usage totals 114,674 output tokens, including reasoning. Individual summaries occupy 13,937–49,090 characters. See `audit.json`.
- The last interval was 328.214 seconds. Service logs show a history summary request ending with 7,930 generated tokens / 285 seconds, followed by a split-turn summary ending with 926 tokens / 43 seconds. This explains the pause without assuming a frozen engine.
- Installed Pi code reserves 16,384 tokens, keeps 20,000 recent tokens, allows 0.8 × reserve for history summaries and 0.5 × reserve for split-turn summaries, and runs the two calls sequentially. Its update prompt asks to preserve previous information and previously completed work. Its provider adapter can add a thinking allowance. Output caps are ceilings, not requested lengths.
- The observed browser mistake was rebuilding/restarting without reloading, then treating identical old measurements as evidence that new CSS failed. After navigating, the panel measured 285px rather than 163px. Further verification continued after success.
- A separate T3 error says: “Insufficient context allowance for the provider handoff. Compact the target conversation or use a larger-context model; the current request has not been truncated.” This is distinct from model generation or summary failure.
- Local session audit found one assistant error marked “This operation was aborted”; it does not establish ten failed compactions. A missing persisted compaction is not proof that no compaction attempt failed or was cancelled.

## Reproduction benchmark

Completed screen:

| Case | Q2_0 | IQ3_XXS |
|---|---|---|
| Stale page, baseline | Pass | Fail: one unnecessary edit |
| Stale page, workflow instruction | Fail: one unnecessary edit | Pass |
| Already verified, baseline | Pass | Pass |
| Already verified, workflow instruction | Pass | Pass |

Both passed 3/4 single trials. Neither failure was an infinite loop: each finished after seven API steps, but made an unnecessary edit after receiving a correct fresh measurement. The screen demonstrates that upgrading to the downloaded Q3 does not eliminate this failure mechanism. It does not establish equal overall quality or prove a quantization-specific cause. Q2 remains the default.

`bench.py` boots Q2 then the already downloaded IQ3_XXS under the same patched engine, 165 W, 128K context, int8 KV, 32K resident KV, MTP4 and borrowing flags. Production is stopped for GPU exclusivity and restored in `finally`; production configuration is checked byte-for-byte. Vision is disabled in this text-only experiment.

The API is `/v1/messages`, matching Pi's provider protocol, but the tools are a **deterministic simulator**, not a real browser and not the full Pi/T3 agent loop. No website files are edited or published.

Two cases, each with and without a short workflow instruction:

1. **Stale page:** source/server version 4 is fixed, loaded page version 1 still measures 163px. Navigate loads 285px. Pass requires finishing within eight requests with a fresh page and zero unnecessary edits.
2. **Already verified:** the latest state is already 285px and deployed. Pass requires finishing without further edits.

Each arm is one stochastic trial with the server's sampling defaults. Model calls permit 1,024 thinking tokens and 2,048 total tokens. Tool input-schema adherence is not scored; state transitions and unnecessary edits are. This screens for a failure mechanism; it is not a reliable quantization ranking or an indefinite-loop reproduction rate.

The first Q2 stale baseline passed. The Q2 stale case with the extra instruction nevertheless edited after a fresh 285px result, and its final report incorrectly claimed the earlier approach had failed. The instruction is therefore **not adopted as a proven mitigation**. This reproduces unnecessary work through Strata without Pi orchestrating the steps; it cannot isolate quantization from the base model, sampling, MTP or engine numerics.

## Real compaction replay and candidate fix

`extract.mjs` uses the installed Pi `prepareCompaction` on the exact branch preceding the last recorded compaction. It recovers the previous summary, history and split-turn prefix. Raw content stays under gitignored, owner-only `private/`.

The initial `summary_probe` combines those inputs and asks for 600 words with a 2,048-token cap. The raw request omits `thinking`; Strata enables reasoning for that request. These results **must not be represented as validation of disabled reasoning**.

`compact-strata.ts` is a separate candidate using Pi's supported `session_before_compact` hook, scoped to provider `strata`. It performs one combined summary request, preserves `firstKeptEntryId` and file-operation metadata, asks for a current-state handoff rather than an accumulating history, and omits the SDK's `reasoning` option so its Anthropic adapter explicitly sends `thinking: {type: "disabled"}`. It rejects capped, empty or incomplete summaries and falls back to Pi's original compaction path. Cancellation leaves the original context intact.

`test-extension.mjs` loads the hook through the actual installed Pi loader and checks retained boundary, file metadata, cancellation and invalid-response fallback. `validate-live.mjs` runs that hook through the installed Pi SDK on the restored service, records the actual outgoing thinking/max-token fields, and saves the summary privately for review. A short summary still needs content review; a terminal marker alone is not a semantic correctness test.

The first successful Q2 SDK replay completed in **58.86 seconds**, with **748 output tokens**, a **373-word** summary, explicit `thinking: {type: "disabled"}`, and the unchanged retained boundary. The source incident was 328.214 seconds / 8,856 output tokens; this is a historical comparison, not a newly paired stock replay. Its 79 retained recent entries include commit `a8b8d73`, fresh 285px measurements and the latest reload instruction. The short summary describes the older cutoff, not the current end of the conversation. The final hook always labels it as historical and directs the model to give newer messages precedence. Metadata from previous custom compactions is explicitly carried forward.

The hook uses **`ctx.modelRegistry.streamSimple(...).result()`**, whose provider-neutral options explicitly disable thinking when `reasoning` is absent. `modelRegistry.complete()` is a different raw-provider path and must not be substituted. The final hook was revalidated after this integration correction.

The initial terminal runner exited 143 during Q3's first case. That incomplete trial was discarded; `resume.py` continued under a transient user systemd unit. The first Q3 hook-validation attempt failed locally on a missing SDK export before making a model request, then restored production in `finally`. This is **not a Q3 summary-quality result**. The import was corrected and the actual hook was validated on restored production Q2. No Q3 compaction speed comparison is claimed.

## Installed mitigation and rollback

The reviewed hook is installed at `${HOME}/.pi/agent/extensions/compact-strata.ts`, only for the `strata` provider. Pi's default resource loader discovers it without errors. Start a fresh Pi session or reload extensions to activate it in an existing process. `installed.json` records the exact file hash. Run `python rollback.py` in this directory to remove it; rollback refuses to remove a file modified since installation.

The normal Q2 borrowing build, 128K context, vision support and 165 W limit are restored. `restoration.json` confirms the production service configuration is byte-for-byte unchanged. The compaction hook is a mitigation with one real historical fixture; it does not claim to fix general agent looping or T3's separate handoff context guard.

## Files and repeatability

- `manifest.json`: engine hash, settings, sampling limitations and protocol.
- `results.jsonl`: per-case measurements; `q*-*.json`: simulated tool traces.
- `audit.json`, `today-session-audit.json`: local session evidence.
- `run-source.py`: frozen source for the first run.
- `live-validation.json`: actual Pi SDK/hook validation, when completed.

Run `node extract.mjs` and `node test-extension.mjs` from this directory. The benchmark refuses to overwrite `results.jsonl`; use a new experiment directory for repeats. Run `node validate-live.mjs` only after production is restored and idle. Never publish the private replay files or credentials.

## Follow-up acceptance criteria

**Later same-day update:** the stronger long-context replay (`../strata-loop-replay-20261021/README.md`) reproduced three edit/build/measure cycles without reload using the actual Pi SDK, ~103K-token saved history and a real browser. Four edits and three rebuilds left the loaded card at 157px; one operator reload changed it to 285px with no further edits. This supersedes the earlier absence of a multi-cycle reproduction, but does not isolate quantization or establish a general fix.

Before declaring Q3 more reliable, repeat both cases over multiple seeds/orders, add a full Pi run with the original long context and tool schemas, and score completion, unnecessary edits, invented conclusions, summary fact retention, total wall time and compaction count. Keep inference flags fixed; test MTP-off or the original engine separately if failures persist. A stronger-model reference must receive the same fixture and tools. No Q3 default switch is justified by one small screen.
