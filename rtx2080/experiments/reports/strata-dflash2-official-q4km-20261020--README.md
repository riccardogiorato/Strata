> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Official Flash-Next DFlash2 Q4_K_M on RTX 2080

Local follow-up on 2026-10-20 to the first DFlash2 experiment (`../strata-dflash2-20261020/README.md`).
The target remains Qwen3.8-Flash-Next GSQ-RCO Q2_0; one RTX 2080 8 GiB / SM75,
64 GiB RAM, SSD storage and the existing 165 W cap. The managed 128K MTP service
is stopped for each laboratory phase and restored afterwards. Its config,
binary and boot service are not replaced.

## Official weights and metadata adaptation

[Official Inco AI GGUF](https://huggingface.co/incoai/Qwen3.8-Flash-Next-DFlash2-GGUF),
revision `4f5a39be8f0a9e9a573ac9824251830a8f4096d9`:

- `Qwen3.8-Flash-Next-DFlash2-Q4_K_M.gguf`, 362,124,704 bytes.
- SHA-256 `2f174e593998c77df0eb7ca13961915a26f25f7944d784a1838e1856e857ff0d`.
- 81 tensors: 45 Q4_K, four Q6_K, 32 F32. Unlike our prior conversion, this
  quantizes convolution projections and selector codebooks as well as the backbone.

`adapt-metadata.py` adds the explicit Strata contract: vocabulary 248320,
mask token 248077, RoPE theta 10000, raw-HC mean features, target layer IDs
already expressed as input boundaries `[6,16,26,36,46]`, and anchor exclusion.
The duplicate tokenizer metadata is omitted because Strata uses the target's
existing tokenizer. **Every tensor name, shape, dtype, offset and payload is
unchanged.** `artifact.json` checks SHA-256 for all 81 tensor payloads.
The adapted artifact is 351,182,720 bytes, SHA-256
`3d26480238d710e705132adbf3ed96817e4a3b2b463a414ad736e207b0eb38d7`.
Both files stay on the SSD at `${HOME}/models/flashnext-dflash2`.
There is no requantization or full-codebook expansion in this adapter.

## Local runtime extension

Source is the same pinned author branch at
`2103f3e4b7fc56cfa3231ecc001ebe0a931a7db9` in
`${WORKSPACE}/strata-dflash2-2080`, associated with
[Strata PR #1961](https://github.com/Niko1221/Strata/pull/1961).
We retain our Turing scorer patch and `STRATA_SM75_PERF=1`.
The preceding experiment's executable is preserved as
`build-turing/strata-before-q4km`, hash
`19f2a291e4582c3b68d5b76b99a0051de86109422fb0bdada49ccd091f9b49fc`.

This follow-up adds:

- Q4_K/Q6_K matrix acceptance for the existing native projection kernels.
- F32 DFlash2 norms/base kernels uploaded as F32 without BF16 rounding.
- Quantized DFlash2 extension projections and matching Q4_K selector codebooks.
- A CUDA selector that decodes only the requested codebook values, keeping
  the large vocabulary codebooks compressed on the GPU.

The BF16 selector route and the plain-DFlash F32-norm refusal are retained.
`runtime-and-turing.patch` captures tracked source changes. Copy the accompanying
`dflash2_q4k_parity.cpp` to `src/kernels/` when reconstructing the patch on a fresh
checkout; it is the newly added test referenced by the CMake change.
`metadata.json` records the new executable and patch hashes. No upstream PR
or issue was submitted or changed; this remains a local compatibility experiment.

Seven selected CTests pass, including the new selector oracle. Its 135 cases
compare Q4_K codebooks to GGML's independent CPU dequantizer, at ranks
256/512/1024, rows 2/4/8 and top-k 1/16/64, including ties. Candidate IDs agree;
confidence tolerance is 3e-5. Existing BF16 operation/loader tests pass.
An initial test attempt ran before the new test target finished building and
also exposed overly broad format acceptance; the guard was narrowed and the
complete checks rerun after the build. `ctest-initial.log` preserves that attempt;
`ctest.log` is the final passing run.

Both the old local Q4 and official Q4_K_M match the two target-only greedy
reference replies with fixed 1,000-slot expert placement, no adaptation/PCIe
sharing, and no lookup/suffix drafts. These small probes check integration;
they do not establish general model quality or output parity at all contexts.
CUDA/SM75 is tested. HIP, SYCL and Windows are not tested.

## Measurement method

One executable and target pack for all arms. Two fresh boots each, order
MTP, local Q4_0, official Q4_K_M, official Q4_K_M, local Q4_0, MTP.
There are 60 seconds between boots. No build or second GPU workload overlaps
model execution. The power cap is 165 W throughout; `gpu.jsonl` samples at 1 Hz.

All arms configure 32,768 context, resident int8 target KV, calibrated PCIe and
adaptation settings, auto expert cache and auto prefill. Draft private KV is
allocated up front. MTP uses spec 4 / floor 0.70; DFlash2 uses spec 4, three
proposals / floor 0.50. The hardware memory budget is the same, while expert
cache and prompt chunk sizes respond to each draft's actual memory use.
This is an artifact comparison, not an exhaustive per-artifact tuner sweep.

The workloads are three 192-output-token short prompts, the existing real
20,066-token coding history, and a 19,462-token real code archive with a needle
at 10% character depth. There is no repeated filler and no prompt-cache reuse
in the standalone measured requests. Temperature is zero and thinking is off.
The coding history ends in a tool call/EOS before the 192-token output cap;
use the actual `predicted_n` when interpreting its decode speed.
An actual Pi bug-fix task runs once for MTP and official Q4_K_M, starting from
fresh failing fixtures and checking protected inputs afterwards. Those wall
times are individual agent trajectories, not general speedup estimates.
OpenCode and Claude Code clients are not run in this follow-up.

| Same-source 32K workload | MTP | Local Q4_0 | Official Q4_K_M |
| --- | ---: | ---: | ---: |
| 20,066-token coding history, prefill tok/s | 777.9–778.6 | 599.1–600.5 | 708.0–713.2 |
| Same history, decode tok/s (30 output tokens) | 43.0–44.5 | 39.6–48.6 | 41.5–48.3 |
| Same history, wall seconds | 26.48–26.53 | 34.07–34.29 | 28.79–29.10 |
| Index explanation, decode tok/s (192 tokens) | 43.8–50.6 | 42.3–46.2 | 45.0–46.2 |
| Merge-function code, decode tok/s (192 tokens) | 61.6–62.2 | 59.6–60.6 | 39.7–60.2 |
| Process/thread explanation, decode tok/s (192 tokens) | 51.3–53.0 | 47.6–49.3 | 36.6–49.4 |
| 19,462-token retrieval archive, prefill tok/s | 807.1–818.6 | 611.3–611.9 | 705.9–707.8 |

Official Q4_K_M prefill improves **17.9–19.0%** over the local Q4_0
conversion on this coding history. It remains **8.3–9.1% below MTP**
in the matched 32K setup. All six retrieval checks passed.

Pi passed with protected files unchanged: MTP 36.25 seconds, official Q4_K_M
36.36 seconds. These are one trajectory each, not proof of equal or better
agent speed. The first official boot's short decode samples were slower than
the second; both are retained in the ranges. Its observed SM clocks stayed
around 1905–1935 MHz and GPU temperature 47–51 C for these short samples.
No controlled cause for the variation was established. No consistent decode
advantage over MTP is claimed. A lightweight web deployment/server in another
project was observed during this phase; no concurrent CUDA build or second
GPU workload was present.

The allocation benefit is reproducible: MTP uses 1,499 expert slots and
2,816-token auto prefill chunks; local Q4_0 uses 1,201 / 1,792; official
Q4_K_M uses 1,342 / 2,304. With full 32K private draft KV, local Q4_0 holds
1,301.3 MiB and official Q4_K_M 1,114.9 MiB (component counters, not total
process VRAM). The new format saves about 186.4 MiB of GPU draft allocation.
It shrinks weights, while the draft's private KV capacity remains the same.

**Verdict:** the official quantization is a useful improvement over our
previous DFlash2 conversion for prompt ingestion. MTP remains the everyday
choice on this RTX 2080. No Q3 target, exhaustive per-artifact tuning,
full AG-Bench suite or general model-quality conclusion is included.


## 128K allocation check

After the matched suite, `fit128.py` tried the same reduced-buffer configuration
as the preceding experiment: full private draft KV allocated up front, spec 4,
512-token prefill, requested 4K target KV residency, and 512 MiB reserve.
The engine again retained a minimum 20,480 target KV cells. Official Q4_K_M
held 3,422.3 MiB for draft weights/pools/scratch. Only 0.13 GiB was free before
auto cache admission; zero expert slots remained, with the engine reporting
about 987 MiB short of its minimum cache plus reserve. Prefill initialization
then failed at `cublasCreate` with status 1. No 128K request completed and no
128K throughput is reported. Logs/config are retained. The prior 128K-capacity
parity probes only used tiny prompts and an initially small elastic draft KV;
they are not a successful long-context test.

The smaller weights reduce memory use but do not solve the full private KV
allocation. This is a limitation of the tested configurations on this card,
not a proof that every possible 128K DFlash2 implementation is impossible.

## Trying it

From the repository root:

```sh
systemctl --user stop strata-serve.service
./strata-dflash2 serve q4km
# Another terminal:
./strata-dflash2 monitor
# After exiting the experimental server:
systemctl --user start strata-serve.service
```

The helper defaults to `q4km` when no quantization is supplied. `serve q4` and
`serve q8` retain the earlier local artifacts. The new recipe is
`recipes/strata-configs/strata-q20-gsq-dflash2-q4km-32k-local.json`.
It uses the separate patched engine and binds only `127.0.0.1:8086` at 32K
configured context. It does not replace `strata-beta` or the boot service.
These throughput tests cover the real 20K history and 19K retrieval archive;
there is no controlled near-32K throughput ladder in this follow-up.

## Launcher verification and cleanup

The actual `./strata-dflash2 serve q4km` command was started after the workload
and allocation tests. Health advertised 32,768 context; a greedy smoke prompt
returned PONG; `./strata-dflash2 monitor --once --output json` succeeded.
The experimental process group was stopped and port 8086 closed. The original
managed beta MTP service was restored, active and enabled, with health showing
131,072 context and API-key protection. Its binary still has the original
SHA-256 `19a2e41f8af5685ce478a61c872b3061e1ee74dbef7384c50e89fb1ebf7f6fb8`.
The GPU power cap remains 165 W. `launcher-smoke.json` and `postflight.json`
record cleanup. Only the original managed engine remains on the GPU.

To reconstruct the isolated build, apply `runtime-and-turing.patch` on the
pinned source and copy the new oracle test source as described above. Use
CUDA architecture 75, Release, `STRATA_ENABLE_CUDA=ON`,
`STRATA_ENABLE_DFLASH2=ON`, `STRATA_NATIVE_EXPERTS=ON`,
`STRATA_MMQ_KQUANTS=ON`, `STRATA_BUILD_TESTS=ON`, and the existing pinned
GGML tree at `${WORKSPACE}/llamacpp-3cf03257`.
`build-cache.txt` records the actual build configuration.

Raw responses, per-boot configs and engine/server logs accompany `results.jsonl`.
`summary.json` contains full ranges. `telemetry-summary.json` uses approximate
phase windows derived from request wall time and engine durations; these are
coarse 1 Hz samples rather than CUDA traces. All new work is local and
uncommitted. The normal MTP service, boot settings, root README leaderboard,
dashboard and application integrations were not replaced.
