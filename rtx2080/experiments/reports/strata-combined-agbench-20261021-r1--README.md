> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Current engine versus combined VRAM loans + PCIe retention

Completed 2026-10-21. Both full AG-Bench suites, both three-repeat standard speed
suites, and the direct real-history comparison completed. The original everyday
service is restored and loaded; its config, executable and source are unchanged.

**Conclusion:** the combined patches are useful for long fresh prompts: the real
122K request saves 30.8 seconds. This rerun does not establish a sustained decode
or whole-coding-task speedup. Keep those claims separate when deciding whether
to adopt the custom build. No production configuration was changed.

## Completed results

The patched build improves long fixed-prompt prefill, but does not improve the
end-to-end coding-task score or time in this single paired suite. Both builds
pass all ten meaningful repair tasks with protected inputs intact. The patched
suite takes 548 versus 523 seconds (+4.8% longer), excluding the known defective
task8 fixture. This is one observation with different agent trajectories, not
proof of a general coding-speed regression.

| Metric | Current engine | Combined patches | Change |
|---|---:|---:|---:|
| Meaningful AG-Bench task passes | 10/10 | 10/10 | Same |
| Those ten tasks, full task time | 523 s | 548 s | 4.8% slower |
| Standard short decode, median | 47.9 tok/s | 48.9 tok/s | 2.1% faster |
| Standard 4K prefill, median | 672.5 tok/s | 674.0 tok/s | Unchanged |
| Standard 16K prefill, median | 692.7 tok/s | 859.1 tok/s | 24.0% faster |
| Standard 32K prefill, median | 689.2 tok/s | 854.5 tok/s | 24.0% faster |
| Standard 16K full request, median | 23.63 s | 19.18 s | 18.8% shorter |
| Standard 32K full request, median | 47.09 s | 38.13 s | 19.0% shorter |
| Scripted cached followup first token, median | 5.071 s | 5.081 s | Unchanged |

### Direct real-history comparison

One fresh boot per arm, same inputs, current then combined. Both long decode
prompts generate exactly 2,048 tokens, for 4,096 output tokens per arm.

| Metric | Current engine | Combined patches | Interpretation |
|---|---:|---:|---|
| Sustained decode, aggregate | 56.60 tok/s | 56.47 tok/s | Effectively unchanged (−0.2%) |
| Coding decode | 61.5 tok/s | 62.0 tok/s | +0.8% |
| Prose decode | 52.4 tok/s | 51.9 tok/s | −1.0% |
| Real 20,064-token prefill | 692.7 tok/s | 825.8 tok/s | +19.2% |
| Real 20K full request | 29.92 s | 24.94 s | 5.0 s saved |
| Real 121,788-token prefill | 690.8 tok/s | 836.3 tok/s | +21.1% |
| Real 122K full request | 177.85 s | 147.04 s | 30.8 s saved |
| 256-token cached followup after 122K | 6.71 s | 6.51 s | One sample; different draft acceptance |

The earlier small combined decode gain does not reproduce in this sustained
pair. The standard short-probe gain is only 2.1%. Taken together, these results
support a strong long-prefill benefit, but not a dependable combined decode
speedup or a universal coding-task improvement. The earlier standalone
retention comparison is still valid evidence for that separate configuration;
it should not be substituted for this actual combined-versus-current result.

The real-history response lengths are 40/30 tokens at 20K and 64/62 at 122K
(current/patched), so full response time is not strictly an equal-output test.
The separately reported prefill counters and the dominant prefill share show
where the large saving comes from. Both cold histories have zero cached tokens.

Both arms also pass retrieval at 19,468 and 121,187 input tokens, returning
identical key answers. The full-length retrieval request takes 177.39 versus
145.66 seconds. `final-validation.json` confirms all four retrieval passes,
zero standard-speed failures, no protected-file violations, unchanged binaries
and original source/config, closed lab port, and the loaded original service.
All 3,618 valid GPU telemetry samples retain the 165 W limit; peak temperature
is 69°C. `context-parity.json` covers all six engine boots (coding, speed and
direct for both arms), not merely the initial coding-suite configs.

Standard prompt probes each repeat three times, short chat comprises nine
100-token requests, and the scripted agent workload comprises three six-turn
sessions per arm. Neither standard suite reports a failed request. Cached-turn
answers have different lengths; their full response times are not an equal-output
speed comparison. Use first-token time and the separate sustained decode probes.

**Context parity confirmed:** both saved AG configs and loaded-engine health
records show 131,072-token capacity, 32,768 resident KV cells, int8 KV,
`--prefill auto:131072` and MTP spec 4. See `context-parity.json`.
Actual coding-agent histories differ because the agents make different tool calls;
the cold standard prompt probes use identical input lengths.

### Coding tasks

All eleven raw and independently audited verifier results pass in both arms;
the headline excludes task8 because it already passes before any work.
The baseline uses 87 actual tool executions and generates 19,636 output tokens
across the ten meaningful tasks; the patched arm uses 77 and generates 20,065.
The aggregate includes different solution paths, package operations and output
lengths even with identical sampling parameters.

| Task | Current seconds | Patched seconds |
|---|---:|---:|
| JavaScript bugfix | 48 | 30 |
| Bank transaction filter | 69 | 104 |
| Seat assignment | 74 | 51 |
| React repair | 72 | 73 |
| Dependency upgrade | 71 | 92 |
| Python bugfix | 19 | 21 |
| JavaScript to TypeScript | 42 | 37 |
| Extra coding task | 44 | 35 |
| Long-context gateway repair | 49 | 74 |
| Access-log analysis | 35 | 31 |
| **Meaningful total** | **523** | **548** |
| Flagged environment fixture, excluded | 375 | 236 |

Including the flagged fixture would yield 898 versus 784 seconds (12.7% less),
but that would be a misleading headline: the apparent saving comes from a task
whose verifier passed before agent work. Its raw evidence remains available.

This reruns the established eleven-task AG-Bench v2.2, three repetitions of
Strata's standard speed suite, and a direct paired comparison on real 20K and
122K coding histories. Both arms retain the Q2_0 GSQ-RCO model, MTP spec 4,
131,072-token capacity, int8 KV with 32,768 resident cells, existing Turing
optimizations, and the RTX 2080's 165 W power limit.

The baseline is the actual installed v0.2.1 executable. The candidate is the
previously tested isolated build combining upstream PR3281 and PR2964,
`../strata-optimization-ab-20261021/bin/prcombined-strata`. It adds
`--vram-elastic`, the six prefill-loan settings from that experiment, and
`STRATA_ADAPT_FETCH=2`. Binary hashes and exact overrides are in `metadata.json`.

## Protocol

- Full AG-Bench: current then patched, eleven fresh task copies per arm,
  900 seconds per task. Pi 1.3.0, temperature 0, seed 42, thinking setting off;
  the existing AG-Bench protocol omits `reasoning_effort` in both arms.
- Standard speed suite: patched then current, fresh server for each,
  `tools/strata_bench.py --runs 3 --long`. Includes short decode,
  4K/16K/32K prefill and scripted multi-turn agent requests.
- Direct real histories: current then patched, fresh boots, 2,048-token
  sustained code/prose generations, real 20,064/121,788-token coding histories,
  a cached followup, and retrieval checks at approximately 19.5K and 121K.
  Cold requests assert zero prefix reuse. Full wall times include restoration.
- All inference is serialized. The controller stops the everyday service and
  restores it in `finally`. No build occurs during these measurements.

Each coding-agent invocation uses bubblewrap with a read-only root, private
home and `/tmp`, and only its current task directory mounted writable from
the host. Old task runs, repository experiments and source fixtures are hidden.
Pi gets a private writable copy of the model/settings configuration, no
extensions/MCP/skills/prompt templates, and no saved session. Networking remains
available for the local model endpoint and task dependency installation.
The verifier runs afterward against the retained work directory. Independent
hash checks protect task instructions, verifiers and task-specific immutable
inputs; original fixtures are checked before and after the suites.

## Limits and preflight

Task8 still passes its verifier before agent work, confirmed again in
`task8-baseline.json`. Its raw result remains visible, but it is excluded
from the ten-task repair-quality/timing headline. This fixture is not silently
changed during a rerun. Timing from one complete suite per arm also depends on
agent trajectories, output length, dependency installation and tool execution;
it is not an isolated engine-speed measurement.

The preceding directory `../strata-combined-agbench-20261021` preserves an
aborted infrastructure preflight: mounting Pi's config read-only prevented
settings/credential lock creation. No benchmark task ran. The service was
restored. This `-r1` run corrects the harness by copying configuration into each
private writable namespace before starting Pi.

`run.py` is the controller; `agentic.frozen.sh` is a frozen copy of the existing
shell harness with isolated output paths, readiness handled by the controller,
retained verifier logs, and automatic source restoration disabled. Its task
prompts/verifiers are unchanged. `results.json`, raw task rows, per-task Pi
traces, engine logs, standard-suite reports and GPU telemetry retain evidence.
