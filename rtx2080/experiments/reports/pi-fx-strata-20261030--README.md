> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Pi vs fx on local Strata — 2026-10-30

<!-- RESULTS START -->
## Results

| Measure | Pi 1.4.0 | fx 0.0.16 |
| --- | ---: | ---: |
| Verified tasks | 20/20 | 20/20 |
| Agent time per suite | 11.01 min | 19.48 min |
| Native output tokens per suite | 28,169 | 62,101 |
| API uncached input per suite | 54,368 | 69,032 |
| Actual engine input reads per suite | 54,368 | 81,340 |
| Native decode tok/s | 60.12 | 67.13 |
| Native prefill tok/s | 331.74 | 372.61 |
| API prefix token reuse | 90.12% | 94.11% |
| Decode expert pool hit | 80.26% | 86.10% |
| Direct PCIe expert routes | 5.99% | 4.46% |
| Tool calls per suite | 110.0 | 113.0 |

On this setup, fx used 77.0% more agent time and generated 120.5% more native output tokens across the same task count. These are descriptive results from two passes, not a universal harness ranking.

### Individual passes

| Pass | Verified | Minutes | Native output | Decode tok/s |
| --- | ---: | ---: | ---: | ---: |
| pi-r1 | 10/10 | 11.32 | 29,386 | 60.42 |
| fx-r1 | 10/10 | 13.55 | 36,198 | 61.43 |
| fx-r2 | 10/10 | 25.41 | 88,004 | 69.80 |
| pi-r2 | 10/10 | 10.69 | 26,952 | 59.79 |

The second fx pass contains two long reasoning outliers (TypeScript migration and gateway specification). They remain in the primary totals. Correctness is evaluated separately from token throughput. Native decode can be faster on repetitive output while the task takes much longer. Agent prefill rates include short incremental reads and are not directly comparable with a fixed 32K/121K prefill speed test.

### Large-context resume probe

One cold initial agent task and one saved-session follow-up per harness. The engine stays loaded between the two turns; this tests hot-engine prefix reuse, not SSD persistence or engine-restart recovery. Both use 131072 context capacity and a 4096-token response cap. Ordinary suites use a 32768-token response cap. Each harness retains its own default compaction threshold.

| Harness / phase | Seconds | Peak API prompt | Native input reads | Native output | Check |
| --- | ---: | ---: | ---: | ---: | --- |
| pi / initial | 137.91 | 105,254 | 104,809 | 748 | PASS |
| pi / followup | 10.63 | 106,113 | 173 | 494 | PASS |
| fx / initial | 600.00 | 115,461 | 437,458 | 4,053 | TIMEOUT; file check passed |
| fx / followup | 106.92 | 115,713 | 36,521 | 3,083 | PASS |

fx hit the 600-second cap on the initial long task. It had written a correct file, but the agent turn did not finish. Three compaction requests kept the large active user prompt and prepended notes, repeatedly invalidating most of the cached prefix. The fourth large prefill was cancelled; its 104,300 actually read tokens are included above from the native cancellation log (five requested tokens were not read). The late cancellation record has no final API usage. The resumed follow-up succeeded, but it continues a timed-out turn, whereas Pi resumes a normally completed turn: this is a recovery observation, not a clean matched successful-resume latency comparison.
Pi uses the corrected pi-long-fixed probe from 2026-10-31, with the same engine hash and effective config. A CPU-only two-process test verified the resume flags before the GPU recheck. The original pi-long follow-up opened a fresh chat and is excluded from the resume comparison; its raw evidence is retained.
This stress probe uses a large inline archive in one user message. fx defaults to compaction at 80% of its usable input window, while Pi uses its own default threshold. It is not a test with matched compaction policy and does not establish behavior for ordinary multi-turn/file-based coding histories. See https://fx.sh/docs/using-fx/context-compaction .

### Accounting and limitations

- API-boundary prompt/cache counts and actual native engine work are reported separately. Reasoning-budget wraps can create multiple engine generations within one API request, reread tokens internally, and insert wrap text. Native output can also include tokens drained while stopping generation. The grouped attribution audit reconciles original input/cache counts, generation times, and output differences against native continuation prompt growth.
- Weighted native rates include every native segment. API prefix reuse uses only API-boundary input counts. Counting only API uncached input would hide internal rereads after a reasoning limit.
- fx JSON usage omitted cached-token fields for this custom endpoint, while the raw Strata API responses reported them. Cache measurements therefore come from the API and engine, not the fx usage summary.
- Identical production MTP, adaptive expert residency and residency-biased routing remain enabled. Harness prompts/tool schemas and model trajectories differ. This experiment does not isolate a particular prompt feature or establish deterministic output at temperature zero.
- Headless coding-agent comparison, not a benchmark of interactive terminal rendering. Agent time includes startup and the agent’s own tools/tests; independent post-run verification and model loading are outside that time.
- Two passes on one desktop; system telemetry is retained. The task set is small and familiar, so perfect fixture scores do not establish broad coding-quality equivalence.
- `summary.json` contains native/API aggregates and per-task evidence. `results.csv` is a flat export. `comparison.html` offers pass selection. Raw requests, outputs and engine logs remain local; no upstream post or PR was made.
<!-- RESULTS END -->

Completed comparison. Results and limitations follow.

Pinned Pi 1.4.0 (our previous benchmark version) and fx 0.0.16. The fx Linux
release archive was checked against GitHub's published SHA-256. Engine and CLI
hashes, model limits, and task fixture hashes are in `provenance.json`.

Same Swift 1.5 Flash-Next IQ2_XS 125B MoE, tuned Strata 0.2.8, RTX 2080,
131072-token capacity, 32768 resident KV, existing RAM session cache, expert
residency routing, fused kernels and prefill VRAM loans. No new GPU tuning.

## Protocol

- Two passes in order Pi/fx/fx/Pi. Fresh engine and identical expert profile seed
  for each suite. Ten scored existing coding tasks; task8 is excluded because
  its verifier already passes without an agent.
- Fresh isolated task directory and harness profile for each task. The same
  `/tmp/work` path is visible to both. Original repository, credentials and prior
  runs are hidden; only the task and isolated profile are writable. Protected
  instructions/tests/data are compared against fixtures after the run.
- Native harness prompts and tools are retained: those differences are what
  this experiment evaluates. No MCP, custom extensions, skills or delegation.
  fx uses full-access within the filesystem isolation to avoid reviewer-model
  calls that have no counterpart in Pi. Session titles are disabled.
- A common streaming proxy fixes temperature 0, seed 42, 32768 maximum output
  tokens and thinking enabled. Pi's UI `--thinking off` does not disable native
  thinking: its model configuration omits provider reasoning controls, and
  the proxy explicitly enables model thinking for both harnesses.
- 600-second agent limit per task. Identical independent verification, with
  errors, timeouts and fixture violations retained, never silently retried.
- Automatic compaction is enabled in both harnesses with their default
  thresholds. Actual context sizes and any compaction requests must be
  reported. A later long-context probe is separate from the natural suite.
- Production is stopped only while the benchmark owns the GPU and restored
  by the controller's `finally` path. Existing production configuration is not
  changed.

## Metrics

Native rates = total newly processed/generated tokens divided by total engine
prefill/decode seconds, not an average of per-request rates. Prefix reuse =
reused / total prompt tokens across requests. Expert pool hit = hits / pool
lookups; direct PCIe routes are reported separately. Neither cache percentage
is a quality score or an efficiency verdict by itself: histories differ.

Also report task correctness, wall time, output tokens (including thinking), uncached
input tokens, tool calls/errors, first-delta latency.
The sandbox wrapper CPU/RSS accounting did not include the agent reliably;
those counters are retained for diagnosis but excluded from comparisons.
System load and GPU telemetry are recorded separately. Strata does not expose
separate reasoning-token usage here; reasoning text presence is checked, and
all thinking tokens remain included in native output counts. API request/response captures live under `runs/` for attribution;
native engine counts are cross-checked against API usage.

fx's advertised 41% reduction is **uncached input tokens versus fx 0.0.15 in
its own caching scenarios**, not a measured advantage over Pi or over Strata.

Sources: https://fx.sh/changelog#v0.0.16 and
https://fx.sh/docs/configure-fx/custom-model-connections .

## Recorder and verification notes

The first scored fx attempt was interrupted by a recorder TypeError while counting
a structured tool error. It is retained as `fx-r1-interrupted` and excluded. The
full fx pass was restarted from a fresh engine after fixing boolean conversion.

Host-side task5 verification inherited unrelated ancestor Node type definitions.
All scored outputs are independently reverified by `reverify.py` in the same
isolated filesystem namespace as the agent; original host checks are retained.
The task5 agent-side verifier passed, and the isolated independent check confirmed
it. No task source or test fixture was changed to make it pass.

## fx repeat on 2026-10-31

An unchanged third fx 0.0.16 pass completed all ten tasks: **10/10**, **35,209 output tokens**, **zero forced reasoning wraps**. Neither prior reasoning loop recurred. All ten API/native accounting checks passed. A scan of every reasoning response found no repeated ten-word sequence within any one response.

The TypeScript task generated 3,590 tokens in total; the gateway task generated 3,005. The earlier long responses alone each consumed approximately 24.6K tokens.

Output totals per ten-task suite: Pi 29,386 / 26,952; fx 36,198 / 88,004 / **35,209**. The new fx repeat used 25.0% more output than the mean of the two Pi suites, not twice as much. Repetitive reasoning occurred in one of three fx suites; this small sample does not establish a failure probability or prove the issue resolved.

**Timing is confounded:** unrelated Blender GPU rendering and CPU-heavy ring-generation work started after the initial exclusivity check. The 1,204.1 s wall time and 37.0 native decode tok/s are recorded for completeness, not treated as a controlled performance comparison. Other jobs were left running.

Same pinned fx/engine binaries, effective engine config, fx settings, task order, temperature 0, seed 42, 32,768 response cap, 24,576 reasoning limit, and 131,072 context capacity. Original paired results remain unchanged. Production service restored and health checked.

Evidence: `fx-r3-summary.json`, `fx-r3-analysis.log`, `fx-r3-reverify.log`, `runs/fx-r3/`, and `fx-r3-control/`. Reproduce with `python3 retry_fx.py fx-r3` only in a fresh copy (the runner refuses to overwrite existing work).
