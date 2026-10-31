> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# DFlash2 on the RTX 2080

Local experiment on 2026-10-20. Qwen3.8-Flash-Next GSQ-RCO Q2_0 target, RTX 2080
8 GiB / SM75, six physical CPU cores, 64 GiB RAM, SSD weights, 165 W GPU limit.
The managed beta MTP service is restored after each laboratory phase. Its boot
configuration and GPU power service are unchanged.

## Source and artifacts

The experimental implementation is the author's `codex/dflash2-main` branch,
pinned at `2103f3e4b7fc56cfa3231ecc001ebe0a931a7db9`, associated with
[Strata PR #1961](https://github.com/Niko1221/Strata/pull/1961).
It is separate from our adopted beta checkout. This is a local evaluation of
that implementation, with our existing Turing scorer patch carried over;
it is not a claim that we authored DFlash2 or that upstream released it.

- Checkout: `${WORKSPACE}/strata-dflash2-2080`.
- Build: `build-turing/strata`, CUDA 13.3, Release, SM75,
  `STRATA_ENABLE_DFLASH2=ON`, native experts and K-quant MMQ enabled.
- Binary SHA-256: `19f2a291e4582c3b68d5b76b99a0051de86109422fb0bdada49ccd091f9b49fc`.
- `turing.patch` preserves our scorer override and benchmark helper. Both
  `STRATA_SCORES_TURING=2` and `STRATA_SM75_PERF=1` remain enabled.
- Official [checkpoint](https://huggingface.co/incoai/Qwen3.8-Flash-Next-DFlash2),
  revision `a22a1744e85c17364dcc54a6a420af7135d4c7f6`.
- Downloaded BF16 safetensors: 1,206,140,008 bytes, SHA-256
  `d6723f2a359eaf33ec0c95f22ae8edda896774020c552296a85e1913b4d3186f`.
- Q4 GGUF: 546,681,536 bytes; Q8 GGUF: 776,057,536 bytes.
  Norm, convolution and selector tensors remain BF16. All artifacts are on the
  SSD in `${HOME}/models/flashnext-dflash2`.

`metadata.json` pins target weight paths, sizes, source, patch and hardware;
`artifacts.json` records the converted file hashes. `pr1961.json` preserves the
PR description consulted. The GitHub PR ref pointed at an older source commit;
we used the author's newer branch with official-checkpoint support and its
attention optimization. Both build logs are retained.

## Validation and method

Passed: six selected CTests (DFlash2 operations, loader, policy, feature taps,
RoPE and owned KV), seven converter tests, two quantizer tests and the BF16
converter's bit-exact self-check. Q4 and Q8 each matched both target-only
reference replies exactly with 1,000 fixed expert slots, no adaptive swaps,
no PCIe sharing and no lookup/suffix drafting. These two small probes do not
establish general output parity. The first target-only command incorrectly
used `--spec 1`; this native pack requires at least 2, so the corrected reference
used `--spec 8` without MTP or DFlash loaded. The failed startup is preserved.

All model execution and builds are serial. No compilation overlaps a serving
session. The power cap stays at 165 W; `gpu.jsonl` contains timestamped 1 Hz
GPU power, cap, SM clock, temperature, memory and utilization samples.

`run.py baseline` measures the adopted beta and the experimental source's MTP
at the standing 128K configuration. Both read all 121,790 tokens of the real
coding history: 691.6 and 691.0 prefill tokens/s respectively. Their 20,066-token
coding rates were 692.0 and 694.2. These are one run each, used as source
regression controls, not confidence intervals.

The coding inputs are the existing real tool/file histories from
`experiments/rtx2080-prefill-20261018/body-code-25k.json` and
`body-code-100k.json`. Filenames are approximate; response timing fields supply
actual token counts. They are not repeated filler. Temperature is zero,
thinking off, output cap 192. Tool-call completion and EOS can end an answer
before 192 tokens; use the recorded `predicted_n` when interpreting decode.
Unique early case markers avoid prefix reuse for measured standalone requests.

## 128K memory failures

The original Q4 setup used the standing streamed 32K target KV residency,
auto prefill, an eight-row verifier and elastic DFlash KV. It completed the
20,066-token coding history at 706.8 prefill / 43.6 decode tokens/s, but the
121,790-token request failed during draft KV growth. Only 221 expert-cache
slots were below the prefill buffer loan, and growth reached its 128-slot floor.
The remaining cache was not available for draft KV. The driver could not map
96 additional chunks. This is a failed long-context request, not a throughput
measurement. The immediately following Pi attempt failed because that engine
had exited; it is not counted as a completed coding benchmark.

`fit128.py` then tried Q4 with full draft KV allocated before auto expert sizing,
a four-row verifier, 512-token prefill, requested 4K target KV residency and a
512 MiB reserve. The engine actually retained a minimum 20,480 target KV cells.
DFlash alone held 3,608.8 MiB, no expert-cache slots remained, and the prefill
GEMM scratch could not fit. Startup failed. Its logs and config are retained.

These attempts do not establish that every possible 128K configuration is
impossible. They establish that this implementation is not a usable drop-in
replacement for our tuned 128K MTP serve on 8 GiB. A rolling or streamed private
draft KV implementation would be further engineering work.

## Matched 32K comparison

`run.py fit32` uses one pinned executable for every arm, the same Q2_0 target,
32,768-token capacity and resident int8 target KV, auto expert cache / prefill,
and our calibrated PCIe/adaptation settings. MTP uses spec 4 and floor 0.70;
Q4/Q8 DFlash2 use spec 4, three proposals and floor 0.50, with full private
32K draft KV allocated up front. Each artifact sizes its cache from the same
8 GiB card. Order: MTP, Q4, Q8, Q8, Q4, MTP, with 60 seconds between boots.
Two measured boots per arm; report ranges, not best-of. This is not a full
per-drafter calibration sweep.

The suite contains three short 192-output-token requests, a 20,066-token coding
history and a 19,462-token code archive with a needle inserted at 10% character
depth. Each MTP/Q4 Pi run starts from a fresh failing JS bug-fix fixture, then
runs its verification script and checks that protected tests/instructions were
unchanged. Pi task wall times are single observations with different agent
trajectories, not controlled estimates of an agent speedup. OpenCode and
Claude Code clients were not run in this experiment.

| Same-source 32K workload | MTP | DFlash2 Q4 | DFlash2 Q8 |
| --- | ---: | ---: | ---: |
| 20,066-token coding history, prefill tok/s | 772.2–779.1 | 597.9–600.4 | 447.1–447.2 |
| Same history, decode tok/s (30 output tokens) | 41.6–44.5 | 46.3–46.7 | 44.8–46.0 |
| Same history, wall seconds | 26.5–26.7 | 34.1–34.2 | 45.6–45.6 |
| Index explanation, decode tok/s (192 tokens) | 50.2–52.7 | 44.6–46.1 | 42.7–44.1 |
| Merge-function code, decode tok/s (192 tokens) | 63.7–64.8 | 59.5–60.7 | 55.4–59.9 |
| Process/thread explanation, decode tok/s (192 tokens) | 50.9–53.2 | 47.4–48.4 | 47.0–47.5 |
| 19,462-token retrieval archive, prefill tok/s | 804.1–813.6 | 611.1–612.8 | 443.3–443.5 |

All six 32K retrieval checks passed. Both completed Pi runs passed their tests
and preserved protected files: MTP 35.64 seconds, Q4 42.30 seconds. Single
agent trajectories do not establish a general timing difference. The failed
Pi attempt after the 128K allocation error is retained separately.

Q4 prefill is 22.2–23.3% slower than MTP; Q8 is 42.1–42.6% slower. On this
20K task the complete request takes 26.51–26.69 seconds with MTP,
34.11–34.24 with Q4 and 45.57–45.58 with Q8. The short-prompt rows show no
overall decode advantage. The 30-token post-fill reply is too small to make
a broad decode-speed claim.

The runtime allocation explains a material tradeoff. MTP has 1,499 expert
slots and auto prefill selects 2,816-token chunks; Q4 has 1,201 slots and
1,792-token chunks; Q8 has 1,034 slots and 1,280-token chunks. The full
32K private draft allocation holds 1,301.3 MiB for Q4 and 1,520.1 MiB for Q8,
compared with MTP's 839 MiB draft load plus its selected output-head rows.
These counters are component allocations, not whole-process VRAM.

**Verdict:** DFlash2 works on SM75 with our existing Turing optimization, but
this tested configuration is a performance regression on our RTX 2080. Keep
MTP as the everyday 128K serve. The separate 32K launcher remains available
for experiments. No Q3 target, BF16 end-to-end workload, exhaustive draft-block
tuning, full AG-Bench rerun, general model-quality claim or upstream submission
is included in this experiment.


## Trying the separate server

From the repository root:

```sh
systemctl --user stop strata-serve.service
./strata-dflash2 serve q4
# Another terminal:
./strata-dflash2 monitor
# After exiting the experiment:
systemctl --user start strata-serve.service
```

Use `serve q8` for the Q8 artifact. This experimental server binds only
`127.0.0.1:8086`, advertises 32K context and uses the existing target weights.
It does not change the default `strata-beta` command or the boot service.
The two configs under `recipes/strata-configs/*dflash2*32k-local.json` reproduce
these settings. Keep only one engine running on this GPU.

## Cleanup and launcher verification

The actual `./strata-dflash2 serve q4` wrapper was started after measurements.
Its health advertised 32,768 context, a greedy request returned PONG, and
`./strata-dflash2 monitor --once --output json` exited successfully.
The experimental process group was stopped and port 8086 closed.
`launcher-smoke.json` verifies the original managed server was restored,
active and enabled, with health reporting 131,072 context and API-key
protection. Its beta binary SHA-256 still matches the pre-existing build.
The GPU cap is 165 W. Only the original managed beta engine remains.

`results.jsonl` and raw responses/logs are the primary measurement evidence;
`summary.json` contains the ranges. `telemetry-summary.json` derives approximate
prefill/decode windows from response wall time and server phase durations;
these coarse 1 Hz windows are not CUDA event traces. The raw samples remain
in `gpu.jsonl`. No service unit, boot setting, application integration, root
README leaderboard or dashboard was changed for this experiment.
The new experiment and launcher are local, uncommitted work.

## Later official-Q4_K_M compatibility extension

The official Q4_K_M follow-up (`../strata-dflash2-official-q4km-20261020/README.md`)
adds compressed selector codebooks and F32 DFlash2 norm support to the isolated
checkout. The executable used for this original experiment is preserved as
`build-turing/strata-before-q4km` with the SHA-256 recorded above. The current
`build-turing/strata` includes that extension. `strata-dflash2 serve q4` still
selects these original local Q4 weights; the helper's new default selects
`q4km`. The managed beta MTP service remains separate.
