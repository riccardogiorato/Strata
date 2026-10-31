> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata 0.2.0-beta on RTX 2080

Release: <https://github.com/Niko1221/Strata/releases/tag/v0.2.0-beta>.
Pinned source `3d1fb48090e8f2cefc22d7b5845fb7f5b71f33fa`; product version
0.2.0-beta, engine version 0.1.45.3. This is a separate source installation at
`../strata-020-beta`, not an update of the adopted 0.1.45 installation.
Model: Qwen3.8-Flash-Next GSQ-RCO Q2_0 125B, RTX 2080 8 GB, i5-9600K,
64 GB RAM and SSD weights. Both engines use 131,072 context cells, int8 KV,
a 32,768-cell resident window, the same draft layer and calibrated settings.

## Try it on this computer

From the root of this repository:

```sh
./strata-beta --version
./strata-beta serve
```

The foreground server stops with Ctrl+C. In another terminal:

```sh
./strata-beta monitor
./strata-beta connect opencode --url http://127.0.0.1:8080 --model local-model --context 128k --check
./strata-beta connect claude-code --url http://127.0.0.1:8080 --model local-model --context 128k --check
```

The wrapper's `serve` command selects
`recipes/strata-configs/strata-q20-gsq-020-beta-local.json` unless you pass
`--config` or `--profile`. This binds to 127.0.0.1:8080.
The wrapper defaults `STRATA_URL` to that same endpoint for monitor/status;
an existing `STRATA_URL` or an explicit `--url` is respected.
`./strata-beta launch` opens the new guided Terminal. For this existing model,
the `serve` command above retains the already calibrated configuration and
reuses the SSD weights, pack, tokenizer, profile and draft layer. It downloads
no models. App configurations are not overwritten by the commands above.
The existing 165 W boot service and the adopted 0.1.45 recipe remain in place.
The beta recipe enables the same local Turing scorer and upstream SM75 series
as the current tuned engine. Images are not enabled in this text comparison.

## Paired speed results at 165 W

Two boots per tuned build, opposite order, same request bodies, no prefix reuse.
Speeds are tokens per second. The long-history filenames are approximate;
these are the actual server-reported token counts.

| Workload | Current 0.1.45 + Turing | Beta 0.1.45.3 + Turing |
| --- | ---: | ---: |
| 20,065-token coding history, prefill | 690.8–691.7 | 688.1–691.6 |
| 20,065-token coding history, decode | 44.5–46.7 | 44.4–47.5 |
| 121,789-token coding history, prefill | 689.7–690.8 | 688.8–688.9 |
| 121,789-token coding history, decode | 47.6–51.9 | 47.0–48.0 |
| Short prompt 1, decode (192 output tokens) | 46.1–49.5 | 51.1–51.7 |
| Short prompt 2, decode (192 output tokens) | 60.8–62.0 | 60.6–62.2 |
| Short prompt 3, decode (192 output tokens) | 51.4–51.5 | 52.3–53.7 |
| Retrieval, 19,472-token code archive | 2/2 passed | 2/2 passed |

Prefill is effectively unchanged: the paired beta differences are −0.39% and
−0.01% at 20K, and −0.28% and −0.13% at 122K. Long-request wall times are
177.58–177.98 seconds current versus 178.09–178.38 seconds beta. Both builds
select 2,048-token chunks and five CPU workers. GPU expert-cache auto sizing
is retained rather than forcing an identical slot count across builds.

There is no reliable overall decode speedup. The first short prompt is faster
on beta, but its pair gains vary from 3.2% to 12.1%; the other two short prompts
are within 4.5%. The 20K tool-call reply is 30 tokens on both builds and matches
semantically (random API tool-call IDs excluded), while its decode difference
changes direction between pairs. The 122K replies differ and finish at 55–66
tokens beta versus 58–59 current; those short tool replies do not establish a
decode regression. Greedy byte identity across engines is not established.

The current and tuned beta builds both passed the real Pi task (40.0 and 45.7
seconds respectively, one task each, different agent trajectories). The task
failed before editing; verifier and tests stayed unchanged. All six beta API
checks passed (prompt and tool call for OpenCode, Claude Code and Pi). The
OpenCode/Claude Code checks simulate their API formats; they are not runs of
those installed clients. Pi itself was run. The Terminal monitor snapshot passed.

The practical result is a working new Terminal and compatible beta engine,
without a demonstrated speed benefit over the already tuned 2080 runtime.
The adopted recipe remains on 0.1.45. The release's new NVIDIA defaults target
SM86/SM60 rather than SM75, and these logs show a RAM-resident expert arena;
the low-RAM/file-tier gains in the release notes are not measurements of this
configuration. No model-quality or full AG-Bench claim follows from these probes.

### Beta without the local scorer patch

One additional boot of the saved upstream beta executable, with the same
calibrated settings and `STRATA_SM75_PERF=1`, but without
`STRATA_SCORES_TURING`:

| Workload | Prefill tok/s | Decode tok/s | Request wall |
| --- | ---: | ---: | ---: |
| 20,065-token coding history | 691.0 | 43.9 | 29.76 s |
| 121,789-token coding history | 688.4 | 51.0 | 178.14 s |
| 19,472-token code retrieval | 669.2 | 52.1 | 29.36 s |

Retrieval passed, and the installed Pi task passed in 34.5 seconds with its
protected files unchanged. All three builds passed that task. The upstream
beta observations sit in the same overall speed band; this run does not show
a useful whole-model gain from carrying the local scorer tile into beta.
One upstream boot is insufficient to rank sub-percent differences. The
existing kernel-only validation and microbenchmark result remain separate
evidence, not a claim of a whole-model speedup on these workloads.

### Launcher verification and cleanup

After the benchmarks, `smoke-launcher.py` started the actual `./strata-beta
serve` shortcut on localhost:8080, checked its 128K health response, read the
default monitor endpoint, opened the interactive Terminal monitor in a PTY,
and quit it with `q`. The monitor and server exited successfully. This
additional startup is a launcher check, excluded from all speed measurements.

All 30 measured requests completed, all five retrieval checks passed, all
three real Pi tasks passed, and all six API compatibility checks passed.
Every measurement server and the sampler were stopped. The final GPU was
P8, approximately 20 W, 0% utilization, 4 MiB allocated, still capped at 165 W.
No listener remained on 8080 or 8086. `postflight.json` records the final checks.
The adopted configuration and engine binary were unchanged.

## Build

The source worktree was created from the exact release tag. CUDA 13.3, SM75,
Release, native experts, K-quant plugin enabled, and the existing ggml checkout
`llamacpp-3cf03257` are used for both generations. The ggml CPU compilation
flags match the existing build apart from the version macro. No engine runs
while a build is active.

```sh
cmake -S ../strata-020-beta -B ../strata-020-beta/build-turing \
  -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=75 \
  -DSTRATA_GGML_DIR="$PWD/../llamacpp-3cf03257" \
  -DSTRATA_NATIVE_EXPERTS=ON -DSTRATA_MMQ_KQUANTS=ON -DSTRATA_BUILD_TESTS=OFF
cmake --build ../strata-020-beta/build-turing --target strata -j 3
```

The unmodified build is preserved as `build-turing/strata-upstream` before
applying `../rtx2080-prefill-20261018/custom-turing.patch` and rebuilding
`build-turing/strata`. The scorer source is unchanged between upstream tags;
the existing opt-in patch applies without edits. The saved upstream executable
has no local scorer patch. These are local SM75 builds, not downloaded release
binary packages. This does not test packaged installers or the desktop app.

The wrapper uses a separate Python 3.14 environment with system packages and
Pillow 12.3.0 / Textual 8.2.8. Dependency installation is recorded in
`python314-deps.log`; this is not a lock of every system Python dependency.

## Measurement method

`run.py` runs one server at a time at the existing **165 W** cap, with 60 seconds
between boots. It leaves the cap unchanged. The order is current tuned,
beta with local scorer, beta with local scorer, current tuned, then upstream
beta with the standing calibrated SM75 settings but no local scorer override.
The first four boots form two opposite-order pairs. Upstream beta has one boot
only; its numbers cannot establish a small speed difference.

Each boot warms the engine, runs three distinct short prompts (192-token cap),
two real coding-agent histories with tools and file reads (about 20K and 122K,
192-token cap), and a retrieval check using real coding text with a key buried
at 10% of character depth. These are real code/document contents, not repeated
word filler. Histories are the preserved requests from the earlier Turing
experiment; their approximate filenames are not token counts. An early trial
marker prevents prefix-cache reuse; engine-reported tokens and cache counts
are recorded and checked. Paired arms receive identical request bodies.

Each of the three builds also runs the installed Pi CLI on a fresh copy of
the cart bug-fix task. The task must fail before editing and pass afterwards;
task instructions, verifier and tests are checked for changes. Agent wall
times depend on the generated trajectory and are not a controlled throughput
comparison. The beta Terminal also checks OpenCode, Claude Code and Pi API
compatibility without writing their configurations, and reads a monitor snapshot.

`results.jsonl` contains every sample, engine timing and response hash, boot,
health, agent verification and cleanup record. `gpu-samples.jsonl` records
one-second board telemetry and host load. Raw server/engine logs are retained.
`summarize.py` reports every measured range and the two matched-pair deltas.
Older results in this repository are not comparison baselines.

This is a speed/compatibility probe, not a full AG-Bench, model quality
evaluation, or a new power-limit sweep. It does not establish performance
for a different model, GPU, power limit or multiple concurrent clients.
