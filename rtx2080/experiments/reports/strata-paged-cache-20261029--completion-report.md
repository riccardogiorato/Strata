> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

### Usual Pi agent suite

One suite per arm, thinking enabled, temperature zero/seed 42, 131072 context capacity and natural task histories (no padding). The scored histories reached 13.6K/14.1K tokens. Every native output/input/cache count matched its Pi assistant usage record. Both arms had zero API errors and zero fixture violations.

| Metric | Persistence off | Persistence on |
| --- | ---: | ---: |
| Scored task passes | 10/10 | 10/10 |
| Ten scored tasks, wall seconds | 626 | 527 |
| All eleven tasks, wall seconds | 763 | 940 |
| Scored generated tokens | 26,404 | 21,529 |
| Scored new-token prefill, tok/s | 356.6 | 362.0 |
| Scored decode, tok/s | 60.48 | 60.57 |
| Prefix-token reuse, % | 87.65 | 86.79 |
| Expert-pool resident hit rate, % | 81.34 | 79.72 |
| Direct PCIe share of all routed experts, % | 5.70 | 6.16 |

The task-balanced geometric decode ratio was 1.0012×: essentially unchanged. The lower ten-task wall time follows fewer output tokens/tool calls; it is not evidence of a cache speedup. Prefix and expert hit percentages also reflect differing trajectories, not a controlled change in their algorithms.

Task8 already passed before model edits and is excluded from the ten-task quality score, as in the previous harness. Its runtime remains visible: 137 seconds off versus 413 on. Across all eleven tasks, output rose from 32533 to 37911 tokens. Native decode time increased 106.7 seconds and prefill 4.3 seconds. The cache performed twelve synchronous saves totaling 62.4 seconds and **zero SSD restores**; RAM won on continuation hits. These account for nearly all of the 177-second whole-suite increase. This run demonstrates the write cost during continuous coding, not faster ordinary coding. All raw tasks, including task8, are retained.

### Usual speed suite

Three repeats per prompt size, same engine/config apart from persistence. No failed or skipped requests. Prompt rates below are medians; chat decode is total generated tokens divided by native decode time. These probes do not grade answer correctness.

| Probe | Off, tok/s | On, tok/s |
| --- | ---: | ---: |
| 4K prefill | 666.9 | 654.6 |
| 16K prefill | 881.9 | 867.2 |
| 32K prefill | 884.4 | 881.1 |
| Short chat decode | 57.5 | 56.0 |

Caching changes reuse and wall time; it does not modify prefill/decode kernels. The full request timings and cache-probe results are in `final-metrics.json` and the two `speed-*` result directories.

### Host-memory allocation

Exploratory one-process run per profile, after the paired campaign. Same 121K branches and checkpoints, then two independent short conversations below the 8K persistence threshold. This separates long-history recovery from native parking of small chats. No cold-SSD restart repeat is included in this allocation sweep. Five-second memory samples can miss shorter peaks.

| Native parked RAM / hot pages | Long A return, seconds | Short A return, seconds | Short reused tokens | Peak RSS, GiB | Peak swap, GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| ram4-hot1 | 6.168 | 0.385 | 5106 | 48.13 | 0.06 |
| ram0-hot4 | 3.277 | 8.789 | 0 | 48.01 | 0.01 |
| ram2-hot4 | 4.311 | 0.360 | 5106 | 48.19 | 0.02 |

`ram4-hot1` means 4096 MiB native parked conversations / 1024 MiB shared hot pages; `ram0-hot4` means 0 / 4096; `ram2-hot4` means 2048 / 4096. Each native pool has one slot. All other tested settings, including the 1024-token save gain, are unchanged. Per-request results and native page-hit bytes are in `summary.json`; actual engine budgets are recorded in `*-engine-info.json`.
