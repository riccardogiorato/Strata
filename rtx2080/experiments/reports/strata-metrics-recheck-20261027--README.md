> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Repeated throughput, cache and agent-quality audit

Status: complete; production restored and protected hashes unchanged. The current audited observations are in `agent-metrics.json`; `report.html` is regenerated as suites complete. No candidate is automatically installed in production.

This campaign answers the concern that an agent's total runtime can increase simply because it writes more tokens or takes more tool turns. It revisits the recent Strata decisions using raw token counts and engine durations, then repeats promising comparisons.

## Workloads and controls

- RTX 2080 8 GB, i5-9600K, 64 GB RAM, 165 W. Same Swift 1.5 Flash-Next GSQ-RCO IQ2_XS model and 131,072-token capacity.
- Eight new full agent suites: two each for production, custom v0.2.7 routing off, custom v0.2.7 routing prior 1.5, and custom v0.2.3 lookup-16. Earlier routing suites remain separately identified; combined counts become three each for the first three configurations and two for lookup-16.
- Fresh engines and the same initial expert-profile bytes per suite. Second-round order reverses the first. GPU temperature, clocks, power and memory observations are saved in `telemetry.jsonl`.
- The usual eleven-task harness is preserved, including task order and private writable workspaces. Task8 already passes before model action; it remains in the run for session-history comparability but is excluded from headline quality, token rates and task wall time.
- Model thinking remains enabled: the established Pi harness does not send `reasoning_effort`, despite its UI `--thinking off` flag. Temperature 0 and seed 42 are unchanged. Agent outputs, tool histories and per-run working-directory paths can differ; these are repeated agent workloads, not bitwise-identical token streams.
- Natural agent histories are reported at their actual sizes, usually much shorter than capacity. Separate controlled tests use approximately 122K input tokens. The previous identical cold 32K and 122K comparisons remain distinct from these warm-prefix tests.
- The controlled phase compares production, lookup-16, HC scratch sharing, GDN split, shared-expert serial execution with quantization reuse, and lookup-chain 2. Two fresh engines per arm, reversed order, one common saved prefix. Novel code runs executable checks; full-file edits use exact Python AST comparison. Quality failures are retained instead of silently dropped.
- Normal Strata serving is restored by each phase's `finally` block. Production executable, config and expert-profile hashes are checked. Bolt is not started. Private candidate builds are reused; no upstream branch or production source is rewritten.

## Existing optimizations included

Every agent arm retains the production baseline: elastic VRAM allocation; prefill MTP/head and repeat loans; PCIe fraction 0.35; KV prefetch; Turing scorer; fused SM75/native-IQ prefill; 8 GiB RAM conversation cache with two slots; and native hot session restore. `baseline-feature-audit.json` checks launched configurations against the saved production config. Engine startup logs confirm prefill borrowing and the fused/Turing paths, rather than merely recording requested flags.

The oMLX-inspired SSD session proxy is not launched by the normal production service or these agent suites. The controlled 122K phase explicitly exercises saved-prefix restoration, but does not benchmark the proxy's hot/cold session eviction policy. Older PCIe retention, parked-buffer reuse and deduplication patches are separate candidates, not implied by the active borrowing flags. Natural short agent histories also do not stress the full 128K capacity; the controlled phase does.

## Metrics and their limits

1. **Decode throughput:** total emitted tokens divided by total engine decode seconds. Includes thinking. Never average per-request tok/s directly.
2. **Prefill throughput:** total newly read tokens divided by total engine prompt seconds. Reused tokens are excluded. Small cached requests include checkpoint handling overhead and can have low new-token throughput despite excellent latency; matched cold tests isolate prefill better.
3. **Prompt-cache token hit ratio:** sum reused tokens divided by sum total input tokens. Also record the fraction of requests with any reuse, and follow-up-only rates excluding each task's initial request. Different agent histories can change these ratios without any cache implementation change; any cached prefix does not mean the entire prompt was cached.
4. **Expert-cache hit ratio:** sum per-request resident decode hits divided by sum pool lookups. Direct GPU reads over PCIe are excluded from that denominator and reported separately using all routed experts. Routing prior changes expert selection, so correctness remains essential.
5. **Speculative acceptance:** sum accepted drafts divided by sum offered drafts. Suffix-lookup acceptance and accepted tokens per suffix window are separate fields. Higher acceptance is not necessarily faster decode: drafting/verification cost and width matter.
6. **KV-streaming hits:** these engine counters accumulate within segments and reset between conversations. Only the final observation and number of detected counter decreases are retained; samples are never added together or treated as a full-suite hit ratio. Expert-cache counters above are per-request deltas and are unaffected.
7. **Agent hit/success ratio:** verified tasks passed divided by the ten nontrivial tasks per suite. Real tool use, fixture integrity and API errors are audited. Tool executions marked as errors are counted separately; an expected failing test while debugging is not itself a failed task.
8. **Wall time, output tokens and tool calls:** retained alongside throughput. The report includes an arithmetic decomposition of decode-time differences into token-count and time-per-token components; this is accounting, not causal proof.

Every agent request is aligned to its Pi assistant event, asserting exact equality of generated, input and reused token counts. Whole-suite repeat ranges are reported. Repeated attempts at the same ten tasks are not thirty independent problems or a broad model-quality confidence interval.

For partial expert streaming, the report also exposes resident hits, pool misses and direct PCIe routes against one common denominator (pool lookups plus direct routes). Raising the direct-streaming fraction can improve the pool-only hit percentage without improving decode. These are counts of logged expert routes, not transfer bytes, effective bandwidth or time stalled on PCIe; skipped experts are outside the denominator. Those missing measurements are not inferred from route counts. Long context can change the VRAM balance between KV storage, expert residency and scratch allocations, so throughput and residency must be read at the measured context size.

The older Maya/Strata DeepSeek comparison has CPU-lane and GPU-streaming counters with different semantics; it is not part of this Swift campaign and its percentages must not be pooled with Swift's expert-cache counters. No new Maya run or cross-engine cache equivalence is implied.

## Historical decisions

`retrospective.json` recalculates twenty focused comparisons from saved request timings. Most previous rejections already used normalized rates: lookup-8, MTP widths 2/6, the AVX2 exact1 kernel and larger scratch layouts are not reversed by this audit. Invalid long-code QFUSE/reuse paths and an inactive-feature run remain excluded from performance claims. Lookup-16 lacked agent validation; small scratch/GDN/serial/chain differences lacked repeated matched confirmation, so those are tested again.

All 110 historical request records were also matched to their engine expert/suffix counters using exact token/draft counts and millisecond timing agreement. Lookup-16's earlier exact-edit gain came with about 13.8 accepted suffix tokens per lookup window versus 3.5 for the baseline, despite a slightly lower suffix acceptance percentage. This is why acceptance alone does not rank speculative performance. The agent campaign tests whether that benefit generalizes beyond copying/editing existing text.

The agent audit also tracks a reply-resume gap: previous prompt tokens plus previous generated tokens minus the next reused prefix. Most observed continuations stay within a few template-boundary tokens; some lose roughly an entire generated reply. PR1536 preserves generated token boundaries against BPE re-encoding, which is a plausible explanation for some gaps. Client formatting can also change the prefix, so this is a diagnostic lead, not a measured PR1536 speedup. Its earlier ordinary-text fixture did not trigger the issue and must not be treated as proof the feature is unnecessary.

Checkpoint-buffer reuse and parked-block deduplication already showed lower cached-revisit latency with identical token reuse. They remain separate cache candidates; their gains cannot be added. Older PCIe retention showed a tentative decode gain on a different binary, but its patch is absent from current production. A config flag alone cannot activate it.

Older Q2_0-model experiments are not pooled with the current Swift IQ2_XS measurements. No unsupported Maya/Swift speed or universal engine gain is inferred.

## Evidence and regeneration

- `run.py`, `metadata.json`, `agent/`: repeated full agent suites and fixture audits.
- `controlled.py`, `controlled-*.engine.log`, `results.jsonl`: matched long-context tests.
- `analyze.py`, `agent-metrics.json`: validated per-request attribution, per-task outcomes, weighted rates, cache/speculation counts and run spread.
- `retrospective.py`, `retrospective.json`: historical raw-timing recalculation and explicit assessments.
- `speed_audit.py`, `speed-audit.json`: twelve historical usual speed suites recalculated with token weighting, per-repeat rates, follow-up latency and the runner's actual “agent hit %” definition (cached input tokens, not task correctness).
- `report.py`, `report.html`: self-contained review artifact.
- `protected.json`, `protected-check.json`, `original-state.json`, `restore.json`: production protection and restoration evidence. Final health is recorded after the full campaign.

Regenerate the analysis with `python3 experiments/strata-metrics-recheck-20261027/analyze.py`, then `retrospective.py` and `report.py` in the same directory. Execution controllers deliberately refuse to overwrite completed evidence; use a fresh campaign directory for another run.

## Completed repeat results

Weighted decode includes thinking; quality excludes the already-passing task8.

| Configuration | Full suites | Decode tok/s | Expert-cache hits | Scored tasks |
|---|---:|---:|---:|---:|
| prod | 3 | 48.06 | 50.92% | 30/30 |
| off | 3 | 47.71 | 50.47% | 30/30 |
| on | 3 | 60.52 | 80.07% | 29/30 |
| lookup | 2 | 47.70 | 50.68% | 20/20 |

The matched 122K restored-prefix results and correctness checks are in `controlled-summary.json` and `report.html`. Production is restored with unchanged protected hashes; see `final-state.json`.

## Final assessment

All eight new agent suites passed their 80 scored task attempts, with no API errors or immutable-fixture violations. Including the initial comparison, production and routing-off each passed 30/30; routing-on passed 29/30 (the initial missing-output failure remains counted); lookup-16 passed 20/20. Routing prior 1.5 delivered 60.52 versus production's 48.06 weighted decode tokens/s, a 25.9% increase. Pool-only expert-cache hits rose from 50.92% to 80.07%; resident hits across all logged routes rose from 43.44% to 75.25%. All follow-up requests had some prefix reuse; token-weighted follow-up reuse was 91.18% versus 92.17%. Different histories can explain that small prompt-cache difference. Routing changes expert selection; these repeated ten tasks do not establish broad quality equivalence. No candidate was promoted.

The six-arm, two-boot restored-prefix phase passed all 24 executable/AST checks. Novel-code decode was production 54.33, lookup-16 55.22, scratch 56.66, GDN 55.15, serial 55.28 and chain 57.58 tokens/s. Exact-edit decode was respectively 59.88, 61.56, 58.28, 59.44, 57.91 and 56.88. Chain's approximately 6% novel-code gain came with a 5% exact-edit loss; scratch was also mixed. Lookup-16's warm-edit gain was only 2.8%, with overlapping repeat ranges and no agent-throughput gain. These results do not justify a general default change. Previous cold-edit lookup gains are a different cache condition, not erased by this result.

Prompt reuse was identical across these controlled arms: 93.603% for new code and 99.994% for the exact edit. First-token times were about 11 seconds and 0.3 seconds respectively **after** restoring the snapshot; the separate disk restore is excluded. These are warm-prefix checks, not new cold-prefill or complete SSD-recovery latency claims. All 24 request records are matched to engine expert/suffix counters in `controlled-summary.json`. No new cold-prefill improvement was found by this campaign; the earlier retained tuning remains the production baseline.

The historical audit covered twenty focused comparisons (110 matched requests) and twelve standard speed suites. Normalizing by emitted tokens did not overturn the main rejected experiments. It did establish that total agent wall time alone had obscured the routing candidate's repeatable decode gain. Review `report.html` for the full comparison and `final-state.json` for restored 128K serving, 165 W and unchanged protected hashes.
