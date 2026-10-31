> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# RTX 2080 prefill and decode experiments — 2026-10-21

Measured on the everyday Q2_0 GSQ model, MTP spec 4, 131,072-token capacity,
32,768 resident target KV cells, and a 165 W RTX 2080. The production recipe
and executable were not replaced. Testing is complete: 20 boots, 22 retrieval
checks (including four at 121K tokens), and 12 executable coding checks passed.
The original service is restored and loaded; its config, executable and source
match their pre-test state. See `final-validation.json` for the final checks.

**Recommendation:** keep MTP and prioritize broader VRAM borrowing for its
repeatable ~22% prefill-throughput improvement (~18% shorter full requests).
PCIe retention is a smaller useful addition: +5.0% sustained decode individually,
and +2.3% over borrowing alone in the single combined pair. The combined
executable is retained in `bin/prcombined-strata`; it has not been installed
as the everyday engine. Fused prefill and MTP-only borrowing are not winners
in these measurements.

## Individual comparisons

Each comparison uses four independent boots in baseline/candidate/candidate/
baseline order. Percentages compare means within a phase, not between phases.
Full request wall time includes prompt processing, memory restoration and the
generated response; engine startup is measured separately and excluded.

| Candidate | 20K request | 122K request | Sustained decode | Result |
|---|---:|---:|---:|---|
| Fused Q2_0 prefill, PR2145 | 2.9% slower | 0.4% slower | Confounded first baseline; see below | No prefill benefit |
| MTP-only borrowing, PR3307 | 4.2% slower | Unchanged | −0.6% aggregate | No useful gain |
| Broader VRAM loans, PR3281 | 29.70 → 24.47 s | About 178.2 → 145.96 s | Unchanged | Prefill winner |
| PCIe retention mode 2, PR2964 | Unchanged | Unchanged | 56.07 → 58.87 tokens/s (+5.0%) | Decode winner individually |

Broader loans increase engine prefill throughput by 21.3% at 20K and 22.4%
at 122K. Actual prefill chunks grow from 2,048 to 4,352 tokens. The 122K
request saves about 32 seconds after accounting for restoration. Its required
elastic allocator changes the decode expert-cache capacity from 1,371 to
1,165 slots; these samples show no material sustained-decode regression.

PCIe retention's longer decode samples generate 2,048 tokens each, with
8,192 measured output tokens per arm. Both paired comparisons favor it.
The estimated milliseconds per target round fall from 46.22 to 44.39
(round count proxy = generated tokens minus accepted draft tokens). This
proxy helps distinguish execution speed from varying MTP acceptance; the
primary result remains elapsed time and output throughput. Cached followups
after the 122K history are also faster on average, but contain only 256
output tokens each and are less stable than the sustained samples.

The other phases use 512-token sustained samples. Fused prefill's first
baseline decoded unusually slowly (44.3/42.1 tokens/s for code/prose versus
54.1/49.7 on the final baseline). Its raw aggregate +12% decode result is
therefore not reliable evidence of a feature gain. The reverse pair is only
about +2% and prefill is slower in both pairs. Initial host load was higher;
the cause of the slow baseline was not isolated. All raw samples are retained.

## Correctness and integrity

### Combination interaction check

`combined` uses the two patches together, with borrowing enabled on both
arms and retention mode 2 enabled only on the candidate. This is one AB
pair, rather than the two pairs used for the individual comparisons.
The 2,048-token code/prose samples total 4,096 output tokens per arm:
aggregate decode rises from 55.98 to 57.25 tokens/s (+2.3%). The target-round
proxy falls from 46.99 to 44.30 ms, while draft acceptance is lower in the
candidate. Do not add the standalone percentages or promise +5% combined.

Full 20K request time is 24.84 versus 24.86 seconds; 122K is 146.01 versus
147.02 seconds. Thus the prefill gain survives combination, within 0.7%
in this pair. The 256-token cached followup falls from 7.29 to 6.40 seconds,
but its changed draft acceptance and single sample limit that comparison.
Both combined-build arms passed short and full-length retrieval and the
executable coding task. Full-length retrieval took 145.11 versus 145.24
seconds and returned identical answers. Both features were confirmed active
in the candidate logs, and repeated long requests reactivated the loan path.

An additional baseline/candidate pair (`elastic-control`) enables
`--vram-elastic` on both arms and changes only the six borrowing settings.
Both retrieve two keys placed at 10% and 75% of a flattened real archive,
with 121,187 actual input tokens, returning identical answers. Full wall
time falls from 175.46 to 144.15 seconds; prefill rises from 693.6 to
845.5 tokens/s. This supports attributing the gain to borrowing rather than
merely the elastic allocator. Both subsequent executable coding tasks pass.
This is one additional pair, not a repeated long-context quality suite.

The elastic engine can warn of less than 512 MiB free before adjusting
the cache. Logs show subsequent cache reduction or temporary borrowing
freeing space; no tested request stalled or failed. This experiment does
not establish behavior under additional competing GPU-memory pressure.

All sixteen boots in the four individual comparisons passed the ~19.5K
archive-key retrieval check. All eight executable Pi cart-bugfix runs passed
their tests and preserved the protected task, verifier and test files.
These are focused regression checks, not a broad model-quality benchmark.

The separate untimed PCIe admission verification run completed successfully:
the upstream hook's last printed counter was 6,175 admission entries with
zero differences; it skips entries already evicted before inspection. The
run reported 6,548 total admissions. All 239 residency-check windows had
zero mismatches and zero missing CPU activation publications. See
`fetch-verify.json` and `fetch-verify.log`. Verification instrumentation is
not enabled during timed benchmarks.

## Revisions, settings and reproduction

Base source: `90767252f420e25223c739d604145ad15911d48b`, plus the existing
local Turing QSA changes preserved in `turing.patch`. Candidate patches are
applied separately to an isolated checkout, built for CUDA architecture 75,
then reversed. Builds and inference never overlap. See `manifest.json`,
`pr*-build.json` and `pr*-built.diff` for pinned revisions and binary hashes.

- [PR2145](https://github.com/Niko1221/Strata/pull/2145): installed implementation,
  `STRATA_PF_FUSED=1`, `STRATA_PF_FUSED_SM75=1`.
- [PR3307](https://github.com/Niko1221/Strata/pull/3307):
  `41bff1d3d02f238cc5f7bda21d787ab19bbc42cd`, `STRATA_MTP_ROOM_MIN=1024`.
- [PR3281](https://github.com/Niko1221/Strata/pull/3281):
  `cf14700f5da34901908f5d12fa0f3437bcc44708`, `--vram-elastic` and
  `STRATA_PREFILL_ELASTIC_LOAN=1`, `STRATA_PREFILL_MTP_LOAN=1`,
  `STRATA_PREFILL_HEAD_LOAN=1`, `STRATA_PREFILL_RETAIN_STARTUP_CHUNK=1`,
  `STRATA_PREFILL_REPEAT_LOAN=1`, `STRATA_PREFILL_REPEAT_MIN_TOKENS=8192`.
- [PR2964](https://github.com/Niko1221/Strata/pull/2964):
  `f8184f25c169f6459b2e2a1524731055f54c5d90`, `STRATA_ADAPT_FETCH=2`.

`run.py` contains the benchmark harness. Each phase header records its exact
executable, flags, order, warmup and power limit. The real coding-history
fixtures are `../rtx2080-prefill-20261018/body-code-25k.json` and
`body-code-100k.json`, measuring 20,064 and 121,788 input tokens here.
Cold-request checks require zero prefix-cache reuse. A separate followup
preserves the actual assistant/tool messages and measures cache reuse.
Temperature is zero; comparisons share the same prompt within each pair.
Output text can differ with execution routing, so response hashes are retained.

`sequence.py` reproduces the three patched individual comparisons after a
completed fused phase. Each run stops the managed service, uses lab port
8086, and restores the service in a `finally` block. Use a new output phase
name to avoid overwriting evidence. `summarize.py` regenerates `summary.json`.
Telemetry, server/engine logs, raw responses and coding-test evidence are
stored beside the results. Timing samples are few; no confidence intervals
or universal speedup claims are implied.

## DFlash2 and 128K draft KV

These experiments retain MTP. They do not fix DFlash2's separate private
draft KV allocation. In the earlier official Q4_K_M evaluation (`../strata-dflash2-official-q4km-20261020/README.md`),
the full-capacity draft allocation crowded out the expert cache and failed
initialization. Tiny prompts with a configured 128K limit did not establish
that real 128K histories work. Smaller draft weights help, but the draft
still needs memory for its own attention history. The temporary prefill
loans tested here do not establish a solution to that long-context issue.
