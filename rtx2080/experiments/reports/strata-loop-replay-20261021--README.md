> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Long-context Pi / Strata loop reproduction — 2026-10-21

**Reproduced with a real browser:** current production Q2 engine, saved ~103K-token conversation, actual Pi SDK tool loop. The model made **4 successful edits, 3 component rebuilds, and 3 measurements of the unchanged page, with zero reloads**. Stopped at the predefined three-cycle failure threshold after **238.975 seconds**. No tool errors, unsupported operations, or compactions occurred in this run.

The browser measured the card at **157px in every cycle**. A fresh tab measured the rebuilt card at **285px**. Reloading the original stale tab, without editing any code, also changed it to **285px**. This confirms a stale-page feedback loop: the model kept changing source in response to measurements from an older loaded document.

This is one fresh reproduction of repeated non-progress, **not proof of an infinite loop, a failure-rate estimate, or proof that Q2 is the cause**. Q3, MTP-off, another engine, and stronger-model controls have not been run on this new fixture. The prior Q3 tests were small simulations, not this test. No production mitigation or model switch was made here.

## Evidence

| Cycle | New edits | Browser card height | Reloads so far |
|---|---:|---:|---:|
| 1 | 1 | 157px | 0 |
| 2 | 2 | 157px | 0 |
| 3 | 1 | 157px | 0 |
| Operator reload after stopping | 0 | 285px | 1 |

- `live-1.json`: outcome, counters and elapsed time.
- `live-1-actions.json`: observable edits, commands, actual browser measurements and model usage; no hidden reasoning.
- `live-1-browser-control.json`: stale and fresh tabs measured against the same rebuilt output.
- `live-1-reload-control.json`: the original stale tab after one reload, with no source changes.
- `original-positive-control.json`: the original incident also contains three edit/build/probe cycles without navigation.
- `live-runtime.json`: config and harness hashes, Pi version and inference settings.
- `private/live-1/`: full session, frozen source files, raw tool trace and browser request/response pairs. Gitignored; do not publish raw conversation history.

The first model request used 102,884 input+cached tokens. The final measurement request used 107,910. One early request reread 102,761 tokens without a cache hit, accounting for about two minutes; later requests reused the cache. This is not a decode-speed benchmark. The final aborted response was caused deliberately by the reproduction threshold.

## What runs for real, and what is isolated

`prepare.py` freezes the original Pi branch at entry `91cfd4f3` (18:59:45.782Z), before the next repeated edit. It retains the saved history and all 26 original tool definitions. `replay.mjs` loads a separate copy through Pi 1.3.0 and resumes its agent directly from the tool result, without adding a new user instruction. It uses the running Strata API, production Q2/MTP settings and a 1,024-token low thinking budget. The custom compaction extension is not loaded in this isolated runtime.

File edits change copies only. A build command in live mode renders the saved `BenchmarkStory.tsx` with React and recompiles its Tailwind CSS. It updates the served HTML without reloading the browser. **This is a component build, not the original full Nitro build or full-project typecheck**; the tool response retains the original build-success format. The live reproduction used only edit, build and browser-evaluate tools.

Actual DOM queries execute through T3's collaborative browser on a dedicated tab at port 8767. No canned dimensions are returned in live mode. Browser tool requests are bridged through `private/<run>/request-N.json` / `response-N.json`. The bridge remaps the original tab ID and navigation URLs to this isolated tab; it normalizes the test URL back to localhost:3000 in tool results. Reloads remain available to the model.

The fixture renders the story component at the original 1,232px content width in a 1,280px viewport, with the real three map images copied from the local site. It does not render the entire application or reproduce all font loading: its old card is 157px rather than the original 163px. This difference is recorded rather than hidden. The key stale-document behavior and unchanged measurements are real.

Other differences from the original incident: Pi SDK instead of the T3 session transport, isolated runtime system prompt/tool declarations, default stochastic sampling, and no network/git publishing. Read-only shell queries run inside bubblewrap against copied files. Original project files, original Pi session and production service configuration are untouched.

## Earlier attempts in this directory

- `baseline-1`: excluded. Canned shell responses to grep/sed were too broad and could create artificial confusion. Stopped after one cycle; frozen code in `replay-v1.mjs`.
- `baseline-2`: one cycle, then a reload. Still used canned DOM responses and eventually hit unsupported finishing tools. **Not a successful reproduction and not a clean completion.** Frozen code in `replay-v2.mjs`.
- `live-1`: real DOM and real component compilation; reproduced three cycles with zero errors or unsupported operations. This is the result claimed above.

## Rerun from this T3 workspace

The live replay needs a T3 browser bridge; `replay.mjs --live-browser` alone waits for browser responses. It does not secretly launch Playwright or operate the original user's tab.

1. Keep production Q2 idle. Run `python prepare.py` only if rebuilding the frozen fixture is intended; the exact source session must still exist.
2. Run `python prepare-browser.py`. Start a loopback static server on port 8767 rooted at `private/live-browser/served` (the recorded run used a transient user systemd unit).
3. Call T3 `preview_status`, then `preview_open` with `reuseExistingTab:false`, URL `http://127.0.0.1:8767/`, and `open:false`. Record its tab ID. Ensure the tab has loaded the **old** source before starting the model.
4. Start a fresh run label with `node replay.mjs <new-label> --live-browser` under `systemd-run --user`. The script refuses to overwrite a run directory. It reads credentials from the running service in memory; no secret is written into source.
5. Service pending browser requests using `bridge-driver.js` inside `functions.exec`, changing its literal run label and setting `bridgeTab`/`bridgeRun` in the functions store. Inspect requests, preserve their expressions, target only the dedicated test tab, and write the actual MCP results back. The frozen driver documents exactly how the successful run was bridged.
6. Run `python analyze.py <new-label>`. Inspect all actions before counting a reproduction. Require three actual unchanged edit/build/measurement cycles, no reload, and no test-environment errors. Tool/time limits alone are not reproductions.
7. Compare a fresh tab and reload the original tab to verify whether source and loaded DOM diverged. Stop the temporary fixture server after recording results.

Limits: 24 executed tools / 15 minutes per run. The existing browser and model inputs make this a repeatable **test procedure**; one successful stochastic run does not establish deterministic reproducibility.

Next causal tests can use this exact fixture: require reload after rebuild before measuring, then compare Q2/Q3 or MTP-on/off separately. A reload guard has not been installed or validated as a general agent fix by this experiment.

## Grok Build exploration

Grok Build 1.0.62 is configured as an additional T3 provider, **Grok · Local Strata**, using `~/.local/bin/grok-strata` and private `~/.grok-strata/config.toml`. Both a direct chat and a native shell-tool smoke test passed against the running local API. Existing provider defaults were preserved.

The long-context replay **does not demonstrate that Grok fixes the loop**. In `grok-live-3`, after recovering from a malformed `use_tool` call, the model made two edits and completed two edit/build/browser-measurement cycles. Both measurements still saw the old 157px card; there were zero navigations. It subsequently attempted restart/deployment operations outside this component fixture. The run was stopped after about ten minutes, before the three-cycle reproduction criterion was met.

This is **inconclusive as a harness comparison**, not a clean Grok failure-rate or timing benchmark. The adapter's build shortcut also intercepted compound commands containing deployment commands and returned build output without executing their other parts. That limits interpretation of later behavior. No deployment or push occurred. Earlier `grok-live-1` and `grok-live-2` attempts are excluded for tool-name/discovery adapter errors.

Other differences: Grok used its own system prompt and MCP `search_tool`/`use_tool`, converted Pi history, omitted one historical image, and received a continuation instruction. Initial input was approximately 98,444 tokens versus Pi's 102,884; Grok's available reasoning budget was 12,288 rather than Pi's 1,024. Long generations were observed, but their attribution to compaction was not established. Do not attribute these results to quantization or use elapsed time to rank harness speed.

Evidence: `grok-live-3-actions.json` contains observable actions and browser values; `grok-live-3.json` contains adapter counters (its build count includes the compound-command shortcut); `grok-live-3-completion.json` records the stop and limitations. Private session data remain gitignored. Temporary test services were stopped; production Strata and the new selectable Grok provider remain available.
