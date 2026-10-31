> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# IQ3 behavior comparison — 2026-10-23

Live status and final table: RESULTS.md (`RESULTS.md`), refreshed by the report worker.
No behavior winner is established until both arms finish.

User authorized stopping Caribbean/production for this benchmark. The controller
stops `strata-serve.service`, boots isolated servers on loopback :8086, and restores
the unchanged production unit/config in `finally`. Production remains Swift IQ2_XS.

## Evidence before the experiment

- Installed engine: Strata 0.2.3, same patched executable for both arms; SHA and
  full configurations are in `protocol.json`. MTP, 128K allocation, 165 W, loans off.
- Available IQ3_S is base Qwen Flash-Next; production IQ2_XS is Swift 1.5 fine-tuned
  Flash-Next. This comparison can select an available model configuration, but
  **cannot attribute differences to quantization alone**.
- Old session analysis recursively counted streamed copies: a historical task5
  sample had 28 counted calls versus 7 actual execution starts. Both the analyzer
  and task12 verifier now count canonical execution starts. Fixture checks also
  verify that five truly identical invocations remain a five-call streak.
- The 16K alias inherited Pi's 16384-token compaction reserve and 20000-token
  recent-history target. That leaves a zero trigger threshold and an oversized
  retention target. The isolated compact arm uses reserve=10384 (trigger=6000),
  keepRecentTokens=1024, the existing custom Strata compaction extension, and the
  original 16K alias. Other tasks retain normal 128K settings. Global Pi files are
  untouched. A task14 result without a completed compaction is inconclusive for
  constraint survival.

## Protocol

Three prioritized tasks, one run per arm, fresh engine boot for every task:

1. task12: Swift IQ2_XS then base IQ3_S; 1200 seconds each.
2. task13: base IQ3_S then Swift IQ2_XS; 900 seconds each.
3. task14: Swift IQ2_XS then base IQ3_S; 2400 seconds each, 16K Pi alias.

Pi 1.4.0, Anthropic messages adapter, thinking medium, same custom compaction
extension. Frozen agentic-bench script, task snapshots, isolated Pi configuration,
and bubblewrap: only the current task is writable; checkout/home/other runs hidden.
No DFlash or borrowing changes. Direct warmup is excluded from per-task engine logs.

`joined.jsonl` joins benchmark rows with corrected session metrics and token-weighted
engine decode throughput. `hit_cap` uses process timeout status rather than fragile
wall-time equality (verification/cleanup can add seconds). `wall_equals_cap` is also
reported literally. Sessions include reception timestamps for stream silence.

Task12's existing verifier additionally demands six score-command invocations,
although TASK.md does not disclose that gate. Quality and verifier output are saved
separately; failure of this gate alone is not evidence of looping. Task13 wording
also both restricts edits to server.js and requests smoke.sh repair; both intended
files are allowed by the controller's immutable-file audit.

One run per task is a screen, not an estimate of stochastic loop probability.
Requested break-even: >=2x lower attractor metrics with <=40% decode loss; if the
baseline does not reproduce attractors, that threshold cannot establish a winner.
Even if met here, model-weight differences prevent a quantization-only verdict.

## Artifacts

- `protocol.json`: frozen configuration, versions, hashes and limitations.
- `analyzer-validation.json`: measurement fixture checks.
- `controller.log`, `results.jsonl`: progress and service restoration.
- `joined.jsonl`: per-task final rows, including verifiers and compaction counts.
- `*.task-engine.log`: generation timings excluding direct warmup.
- `/tmp/agentic-run/behavior-023-<arm>-t<id>/<task>/`: task work and session.
- `private/`: retained raw agent sessions, ignored by Git.

## Resume after startup timeout

The first attempt completed Swift task12 (quality 81.0, no repeated-command
streak, but timed out at 1200 seconds). IQ3 then exceeded the controller's
300-second loading deadline before any benchmark request. Production restoration
was independently verified in `attempt1-restoration-verification.json`. The resumed
controller retains the completed row and uses a 900-second startup allowance for
all remaining boots; task caps and engine settings are unchanged. Failed startup
logs are retained, and resumed labels end in `-r2`.
