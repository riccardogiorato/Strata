> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Strata 0.2.1 installation on RTX 2080

Installed on 2026-10-20 from release tag `v0.2.1`, pinned source
`90767252f420e25223c739d604145ad15911d48b`. Product/Terminal 0.2.1, engine 0.1.46.
The separate source installation is `../strata-021`; the previous
`../strata-020-beta` installation remains available for rollback.

The managed user service `strata-serve.service` now starts this engine at boot.
It retains the existing Qwen3.8-Flash-Next GSQ-RCO Q2_0 125B SSD weights,
MTP, int8 KV, 131,072 context capacity, 32,768 resident KV cells, calibrated
settings, API-key authentication and localhost/tailnet endpoint on port 8080.
The GPU cap remains 165 W. No models were downloaded or moved.

The existing local Turing scorer patch applies cleanly and is retained with
`STRATA_SCORES_TURING=2` and `STRATA_SM75_PERF=1`. Its activation is confirmed
in the engine log. This installation does not include experimental DFlash2.

## Commands

`strata --version` reports the new Terminal and engine build. `strata monitor`
can use `--credential-env STRATA_API_KEY` with the configured key in that
variable; `strata-mon` already supplies the existing connection credentials.
`strata-serve [q20|q3]` starts the corresponding updated tailnet configuration
only when port 8080 is free. The managed service normally owns that port.
`./strata-current` is the repository wrapper for the new release;
`./strata-beta` still explicitly selects the preserved beta installation.

The existing T3/Pi model ID remains `strata/local-model`, context 128K.
The server's API model ID remains `local-model`. Its About/props engine
version is now 0.1.46; that number is separate from product 0.2.1.

## Verification

One real coding-agent history contained **121,797 server-reported input
tokens**, with no cached prefix. It completed in 177.96 s: prefill
**691.5 tok/s**, 64 output tokens at **38.7 tok/s**. A separate real-code
archive with a needle at 10% of character depth used 19,462 tokens;
retrieval passed, with prefill 689.5 tok/s and 13 output tokens at 48.9 tok/s.
These are single installation checks, not a paired speed comparison or a
new performance record. They do not establish a speedup or regression.

Local and tailnet health checks report loaded=true, context 131072 and
API-key authentication enabled. Unauthenticated model listing returns 401.
The Pi, OpenCode and Claude Code compatibility checks each passed both
prompt and tool-call checks. These simulate the clients' API formats;
no new full agent task or AG-Bench suite was run. The monitor snapshot passed.
The service is active and enabled. Only the managed engine remains running.

## Build and evidence

CUDA 13.3, Release, SM75, native experts and K-quant support; ggml commit
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. Build parallelism was 3. The server was stopped during
compilation to avoid overlapping the model's RAM allocation with CUDA builds.
No build errors occurred. No new standalone kernel test suite was run;
the unchanged local patch has its earlier validation, and the installed
model passed the requests above.

The Python 3.14 environment uses system server packages with separately
installed Pillow 12.3.0 / Textual 8.2.8. `python-deps.log` records the additional
packages; this is not a lock of every system Python package.

`metadata.json`, `runtime.patch`, `build-cache.txt`, `configure.log` and
`build.log` pin the source, patch, binary and build settings. `validation.json`,
`validation.jsonl`, response files, compatibility outputs and `monitor.json`
retain verification evidence. The current engine log is
`../strata-021/chat-q20-gsq-021-tailnet.engine.log`.

## Rollback

The original boot unit is saved as `strata-serve.service.before`. To restore
it, stop the managed service, copy that file back to
`~/.config/systemd/user/strata-serve.service`, run `systemctl --user daemon-reload`,
then start `strata-serve.service`. The `strata-serve.before-install` and
`strata-mon.before-install` files preserve the earlier helper commands.
The new `~/.local/bin/strata` symlink points at `strata-current`; remove it
if returning all terminal commands to the earlier arrangement. The original
beta binary and configurations have not been changed.
