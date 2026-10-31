> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata 0.2.9: repeated-thinking investigation and recovery

**Current production, 2026-10-31:** custom Strata **0.2.9 / engine 0.1.55**, **`STRATA_ROUTE_PRIOR=1.5` restored at the user's explicit request**, and `"reasoning_loop_recovery": "close"` retained. The restarted production engine, chat, tool calling, authentication and all configured environment values were verified (`routing-restored.json`). 128K capacity and the existing CPU vision configuration are preserved; image inference was not rerun.

This is the routing-on profile that passed 10/10 coding tasks at 62.16 native decode tok/s and measured 846.76 tok/s cold prefill at 121K. Those are the completed benchmark results below, not new benchmark measurements from the restoration smoke checks.

The initial deployment used routing off as a conservative precaution. The user subsequently chose to restore its speed benefit. `deployment.json` and `reviewed-candidate.json` preserve that initial routing-off deployment; `routing-restored.json` and `final-state.json` record the current routing-on state. The experiments have not established routing as the original loop's cause. The loop-closure mode is a **local patch**, not an upstream fix.

Config: strata-swift15-iq2xs-gsq-029-tailnet.json (`../../recipes/strata-configs/strata-swift15-iq2xs-gsq-029-tailnet.json`). The service, CLI shortcut and monitor use `../strata-029-custom`.

## What the evidence establishes

The earlier fx run contained three repeated-thinking responses: TypeScript requests 008 (6,888 output tokens) and 010 (24,659), and gateway request 005 (24,731). The two largest responses reached the automatic 24,576-token thinking budget. This was not twice as much useful coding work.

The captured loops occur in the model’s generated reasoning before its next tool call, rather than a harness repeatedly executing a tool. The fix is therefore at the server layer and is not tied to fx prompts. A full Pi suite on this candidate has not been run.

The previous production config left `reasoning_loop_recovery` disabled. Its enabled single-token guard cannot detect a phrase or paragraph cycling across different tokens. Replaying all 478 saved reasoning responses through the upstream passage detector flagged those three responses and no others. This is a retrospective corpus check, not proof that the detector has no false positives.

Residency-biased routing (`STRATA_ROUTE_PRIOR=1.5`) changes expert selection. Upstream disabled its automatic small-card default after repetition reports. Our config explicitly retained it. It is a plausible contributing factor, but these experiments have not isolated it as the cause: the exact failing requests completed normally on fresh 0.2.8 and fresh 0.2.9 engines with routing on or off.

A natural TypeScript loop did recur in the 0.2.9 routing-on guarded replay. The new guard detected it at 2,048 generated tokens, then the model made a shell tool call. The entire API response used 2,321 tokens. See `probe-new-close.server.log` and `probe-new-close-ts-second.result.json`.

## Local fix

Source: `../strata-029-custom`, upstream release commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`, with the existing 17-file RTX 2080 tuning preserved. The engine is 0.1.55; the Terminal is 0.2.9.

The opt-in setting `"reasoning_loop_recovery": "close"` uses the existing repeated-passage detector and the existing token-budget closure path. On detecting repeated thinking, it closes the thought and lets the same model continue to an answer or tool call. It preserves the prompt, sampling settings and total output limit. Injected closure tokens count against that limit. Recovery is attempted once.

The existing `recover` mode instead requires a specific system effort sentence and changes sampling for its retry. Those behaviors and the default-off path are unchanged. The local patch is `loop-close.patch`; its code commit is `0fded4a`.

Only generated reasoning is inspected. This does not detect every possible semantic loop, arbitrary repeated tool workflows, or repeated final-answer content. Useful repeated reasoning can also trigger the heuristic. Full task verification remains necessary.

GPU validation here is text-only on one RTX 2080. Existing CPU vision configuration is preserved, but image-triggered recovery and other hardware/platforms were not validated.

## Validation

- SM75 CUDA release build completed.
- 26 focused old/new recovery tests passed, including unchanged normal output, tool-call continuation, cancellation, preserved sampling and shared output caps.
- Server discovery ran 1,306 tests: two timing-sensitive failures and 14 skips; both failures passed an isolated rerun. The final eight new-mode tests also passed after their additions. See `server-tests.log`, `server-tests-recheck.log`, and `loop-tests-final.log`.
- All three captured failures were intercepted in a CPU server replay with a mocked continuation. This verifies control flow only.
- Six live fault-injection tests (three captured failures × routing on/off) supplied the recorded looping tokens, then used real GPU inference for the continuation. All six emitted tool calls after the guard intercepted at 1,024 or 2,048 tokens. Every returned call also validates against the original request’s JSON tool schema (`tool-schema-validation.json`). The injection is confined to `live_recovery.py`; production has no injection hook. These are not throughput or natural failure-rate measurements.
- Both full isolated fx coding suites passed 10/10 tasks (20/20 total), with all 20 API/native accounting checks passing. The routing-on run had one detector intervention at 2,560 output tokens; the task still passed. The routing-off run had none. One run per profile does not establish a loop probability.
- All three usual speed suites passed with no skipped checks; all 12 near-128K cold/warm correctness checks passed.

## Full coding-suite comparison

Same fx 0.0.16 harness, fixtures, tool execution, temperature 0/seed 42, thinking on, 128K capacity and 32,768 output cap. Both candidates use loop closure. Native token rates are weighted by the corresponding measured time, not total task duration.

| Metric | Routing 1.5 | Routing 0 |
|---|---:|---:|
| Independently verified tasks | 10/10 | 10/10 |
| Native output tokens | 40,543 | 40,769 |
| Native decode tok/s | 62.16 | 49.59 |
| Native prefill tok/s | 364.04 | 342.45 |
| Expert-pool cache hit | 80.42% | 51.17% |
| Prefix reuse | 93.34% | 94.33% |
| Task wall time | 907.64 s | 1,055.35 s |
| Detector interventions | 1 | 0 |

Routing off cost 20.2% decode throughput and 16.3% wall time in this paired suite, with only 0.6% more output. This is a measured tradeoff, not a version regression. The prior unguarded fx-r2 output explosion is not used as a clean performance baseline. No other GPU workload was observed during these new coding suites. CPU/RSS figures collected through the sandbox wrapper are not reliable and are not used.

## Standard throughput controls

Three measured repetitions per case, same benchmark client and machine, with 128K capacity. Short chat inputs and 4K/16K/32K cold prompt probes are separate workloads from the full thinking-enabled coding suite above. Every profile finished with no failures or skipped checks.

| Weighted native rate | 0.2.8, routing 1.5 | 0.2.9 + close, routing 1.5 | 0.2.9 + close, routing 0 |
|---|---:|---:|---:|
| Chat decode tok/s | 57.63 | 56.89 | 45.24 |
| 4K prefill tok/s | 656.27 | 655.07 | 660.53 |
| 16K prefill tok/s | 866.59 | 864.86 | 871.80 |
| 32K prefill tok/s | 878.40 | 880.42 | 882.26 |

Holding routing fixed, the upgrade changes these token rates by −1.3% to +0.2%, with no material regression. Disabling routing is a separate intentional decode tradeoff. See `speed-weighted.json` and each `speed-*` result directory.

## Near-128K context controls

Each request contained 121,016 input tokens. Fresh-engine cold/warm pairs ran in order old → on → off → off → on → old. All 12 returned the expected `cached_value()` implementation. The warm request reused 121,009 tokens every time (99.994% of its prompt).

| Profile | Weighted cold prefill tok/s | Warm response wall time |
|---|---:|---:|
| 0.2.8, routing 1.5 | 843.28 | 1.51–1.56 s |
| 0.2.9 + close, routing 1.5 | 846.76 | 1.43–1.52 s |
| 0.2.9 + close, routing 0 | 846.82 | 1.55–1.64 s |

These are short-answer correctness/cache probes, not sustained decode measurements at 121K. They exercise existing warm prefix reuse, not an SSD cache or a server-restart restore. See `long-weighted.json`, `results.jsonl`, and the `long-*.complete.json` markers. The upgrade with routing held fixed changed long prefill by +0.4%.

## Recovery near the context limit

The final fault-injection test used routing off and **118,515 input tokens**. The original 32,768 output allowance was fitted to 12,549 tokens to stay inside the 131,072 context capacity. The guard intercepted the recorded loop at 1,024 generated tokens, inserted 18 closure tokens, and the real native engine then generated 130 tokens containing two valid `grep_files` calls (`supersede` and `gateway`, both in the task’s docs directory). Both calls validate against the original request’s tool schema.

The response used 1,172 total output tokens and one recovery. The continuation read 119,557 actual tokens, including the supplied loop and closure. This is a controlled recovery test, not a naturally occurring high-context failure or a throughput measurement. The tools were validated but not executed in this standalone test; the full coding suites above execute tools and verify finished tasks. See `live-recovery-long-0-gateway.json` and `live-recovery-long.log`.

## Reproducibility and artifacts

The original Swift 1.5 Flash-Next IQ2_XS weights, 131,072 context capacity, 32,768 resident KV, MTP, PCIe access, fused IQ prefill, VRAM loans and RAM session cache are retained. Probe requests preserve the original temperature 0, seed 42, 32,768 output cap and native thinking enabled. The candidate uses the same initial expert-profile seed per engine boot.

`probe.py` replays the exact three captured request bodies without executing their returned tools. `agent_campaign.py` runs the complete ten-task suite with actual tool execution in the original isolated filesystem setup. Verification occurs in the same namespace to avoid unrelated host TypeScript dependencies. API/native usage attribution uses the prior audited accounting functions, including internal continuations.

`performance.py` runs the usual three-repeat speed suite and two fresh-process near-128K cold/warm checks per arm. `analyze.py` keeps correctness, output volume, weighted native token rates, prefix reuse, expert-cache hits and guard events separate.

Deployment was gated on `reviewed-candidate.json`, completed task verification and reviewed speed results. `deploy.py` verifies protected files and the binary hash, checks production health/chat/tool calls/authentication, and restores saved files on failure. Manual rollback: `python3 experiments/strata-029-loop-fix-20261031/rollback.py` (restores the original 0.2.8 configuration, including routing-on and no loop-closure guard).
