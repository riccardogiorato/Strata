> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Normal Strata configuration benchmark comparison

This checks the actual normal configuration after deployment, then the complete previously selected tuning profile. The earlier compute campaign used a different profile; its 10.3% isolated fusion result did not establish the gain of the minimal production deployment.

RTX 2080 8 GB, i5-9600K, 64 GB RAM; Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS. Every measured configuration uses 131,072-token capacity and 165 W. Endpoint and log paths were isolated, and each engine used an identical copied expert profile. The normal CPU-vision configuration was retained; these are text-only benchmarks.

## Usual speed suite

The established `tools/strata_bench.py --runs 3 --long` suite covers nine short-chat requests, three fresh requests each at approximately 4K/16K/32K, and three multi-turn synthetic agent conversations. Values below are suite medians. Conversation trajectories and output lengths can differ; generation medians are not an identical-token microbenchmark.

| Metric | Previous normal | Fusion flags only | Complete tuned profile |
|---|---:|---:|---:|
| Chat generation, tok/s | 45.50 | 43.50 | 47.20 |
| 4K prefill, tok/s | 583.30 | 567.30 | 663.70 |
| 16K prefill, tok/s | 611.10 | 600.80 | 916.90 |
| 32K prefill, tok/s | 607.20 | 606.40 | 926.20 |
| Conversation generation, tok/s | 46.40 | 41.90 | 44.70 |
| Conversation first token, s | 5.55 | 5.37 | 5.14 |
| Conversation cache hit, % | 69.66 | 69.63 | 69.63 |

Previous normal: 0 failed requests; 0 skipped tests. Raw results: `before-speed/2026-10-26-community-rtx-2080-local-model/results.json`.

Fusion flags only: 0 failed requests; 0 skipped tests. Raw results: `after-speed/2026-10-26-community-rtx-2080-local-model/results.json`.

Complete tuned profile: 0 failed requests; 0 skipped tests. Raw results: `tuned-speed/2026-10-26-community-rtx-2080-local-model/results.json`.

## Cold 122K file edit

Each request provides 122,451 input tokens, starts in a fresh engine with zero prefix reuse, and asks for the complete same Python file with a literal changed. The expected AST is checked independently. Startup time is excluded. These file-edit requests explicitly use reasoning_effort=none; their archived responses contain no reasoning output. Previous/minimal-deployment runs use before/after/after/before order; the two complete-profile runs follow those screens, so their comparison is repeated but not interleaved ABBA.

| Configuration | Runs | Prefill tok/s | Generation tok/s | Full request seconds |
|---|---:|---:|---:|---:|
| Previous normal | 2 | 590.1 | 54.4 | 234.03 |
| Fusion flags only | 2 | 601.4 | 57.0 | 228.93 |
| Complete tuned profile | 2 | 886.3 | 60.0 | 162.23 |

Exact full-file checks: 6/6 passed.

## Usual AG-Bench

The usual 11 tasks run once per arm with the same Pi 1.4.0 executable, a 900-second task cap and 128K capacity. Pi requests thinking off, but actual server responses contain reasoning; this is not a reasoning-disabled AG-Bench. Provider settings are identical in both arms. Their natural task contexts are used; they are not artificially padded to 122K. The agent sees only its current task work area, and the audit checks tool activity, immutable fixtures and model errors. Task8 already passes before repair, so the main comparison excludes it. One paired suite measures different agent trajectories, not an isolated kernel speedup.

| Configuration | Audited passes out of 11 | Passes excluding task8 | Task time excluding task8 | Generation excluding task8 |
|---|---:|---:|---:|---:|
| Previous normal | 11 | 10/10 | 650 s | 48.4 tok/s |
| Complete tuned profile | 11 | 10/10 | 700 s | 47.0 tok/s |

For completeness, all eleven raw task times total 1077 versus 899 seconds, with 39,687 versus 32,315 generated tokens. Those totals include task8, whose verifier already passes before work; the ten-task comparison above is the timing headline.

The ten included tasks generated 22,859 tokens before and 24,495 with tuning (7.2% more). Task time increased 7.7%. At the earlier generation rate, the additional tokens alone account for about 33.8 seconds of the 50 extra seconds. The measured generation rate was also lower, 48.42 versus 47.05 tok/s, on different output text. This does not isolate an engine regression, and it does not demonstrate a general agent-task speedup.

New prompt tokens read also differed: 53,975 versus 58,490. `agent-compute.json` aligns each task's Pi output-token totals with its native engine timing records; every token total matches. `agent-details.json` confirms that both arms completed all eleven agents and actually emitted reasoning.

## Configuration difference and selection

The minimal deployment changed only the engine and three prefill-fusion flags. Normal automatic sizing selected 1,792-token prompt chunks. The complete candidate uses the earlier selected 4,096-token prefill, expert-cache and VRAM-loan settings, plus hot session restore. Its total gain versus the old normal configuration cannot be attributed to fusion alone. The 4K value is a processing chunk size; context capacity remains 128K. Vision, networking and model/context identity are preserved.

`metadata.json`, `tuned-profile.json`, generated server configs and engine logs preserve exact settings. `agent-metadata.json` pins the coding harness; `agent-results.json` contains audited per-task outcomes. `summary.json` is generated by `summarize.py`. Benchmark failures and rejected candidates remain in the evidence.

The complete tuned profile was selected for context-heavy work: it substantially reduced the repeated 122K request time and preserved all eleven audited AG-Bench passes. It is not claimed to improve general agent-task wall time; the matched AG-Bench run took 700 versus 650 seconds excluding task8, with 7.2% more generated tokens. Its inference arguments and environment now replace the minimal three-flag deployment in the normal Strata recipe. Vision, network, model and 128K capacity settings are preserved. The installed executable is the same tested fused build. Bolt and 225 W were restored; the selected configuration takes effect on the next Strata start.
