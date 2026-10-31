# Experiment archive

The current production settings are in [`../profile.json`](../profile.json). Historical reports retain rejected candidates and limitations; an archived result is not an enabled feature.

Active research branches:

- `experiment/persistent-prefix-cache`: oMLX-inspired serialized prefix pages, measured restart/eviction gains, synchronous save costs; not production.
- `experiment/iq1m-fused-prefill`: TensorFold-inspired IQ1_M adapter and upstream draft PR history; not production.

The earlier whole-session SSD proxy and its regression tests are preserved in [`snapshot-proxy/`](snapshot-proxy/README.md), alongside the newer native page-cache branch.

Older source variants are Git tags under `archive/2026-10-31/`, indexed in `source-history.json`. Current speed checks: `python rtx2080/manage.py bench`. Full historical machine harnesses and raw evidence remain in the local runtime archive / original benchmark workspace; reports below are sanitized publication copies.

| Campaign | Report | Measurements / patch |
|---|---|---|
| pi-fx-strata-20261030 | [report](reports/pi-fx-strata-20261030--README.md) | [summary](measurements/pi-fx-strata-20261030--summary.json) |
| rtx2080-prefill-20261018 | [report](reports/rtx2080-prefill-20261018--README.md) | [summary](measurements/rtx2080-prefill-20261018--summary.json) |
| strata-0145-agbench-20261018 | [report](reports/strata-0145-agbench-20261018--README.md) | See index.json |
| strata-020-beta-20261019 | [report](reports/strata-020-beta-20261019--README.md) | [summary](measurements/strata-020-beta-20261019--summary.json) |
| strata-021-20261020 | [report](reports/strata-021-20261020--README.md) | See index.json |
| strata-022-default-20261022 | — | See index.json |
| strata-023-default-20261023 | — | See index.json |
| strata-0242-build-20261024 | — | See index.json |
| strata-027-default-20261028 | [report](reports/strata-027-default-20261028--README.md) | See index.json |
| strata-027-routing-20261027 | — | [summary](measurements/strata-027-routing-20261027--summary.json) |
| strata-028-upgrade-20261030 | [report](reports/strata-028-upgrade-20261030--README.md) | [summary](measurements/strata-028-upgrade-20261030--summary.json) |
| strata-029-loop-fix-20261031 | [report](reports/strata-029-loop-fix-20261031--README.md) | [summary](measurements/strata-029-loop-fix-20261031--summary.json) |
| strata-claudecode-agbench-20261022 | [report](reports/strata-claudecode-agbench-20261022--README.md) | See index.json |
| strata-codex-agbench-20261022 | [report](reports/strata-codex-agbench-20261022--README.md) | See index.json |
| strata-combined-agbench-20261021-r1 | [report](reports/strata-combined-agbench-20261021-r1--README.md) | [summary](measurements/strata-combined-agbench-20261021-r1--summary.json) |
| strata-compute-20261026 | [report](reports/strata-compute-20261026--README.md) | [summary](measurements/strata-compute-20261026--summary.json) |
| strata-conversation-cache-20261020 | [report](reports/strata-conversation-cache-20261020--README.md) | See index.json |
| strata-correctness-20261023 | [report](reports/strata-correctness-20261023--README.md) | See index.json |
| strata-dflash2-20261020 | [report](reports/strata-dflash2-20261020--README.md) | [summary](measurements/strata-dflash2-20261020--summary.json) |
| strata-dflash2-official-q4km-20261020 | [report](reports/strata-dflash2-official-q4km-20261020--README.md) | [summary](measurements/strata-dflash2-official-q4km-20261020--summary.json) |
| strata-iq1-prefill-20261029 | [report](reports/strata-iq1-prefill-20261029--README.md) | [summary](measurements/strata-iq1-prefill-20261029--summary.json) |
| strata-iq3s-20261022 | [report](reports/strata-iq3s-20261022--README.md) | See index.json |
| strata-loans-default-20261021 | [report](reports/strata-loans-default-20261021--README.md) | See index.json |
| strata-loop-compaction-20261021 | [report](reports/strata-loop-compaction-20261021--README.md) | See index.json |
| strata-loop-harnesses-20261022 | [report](reports/strata-loop-harnesses-20261022--README.md) | See index.json |
| strata-loop-replay-20261021 | [report](reports/strata-loop-replay-20261021--README.md) | See index.json |
| strata-metrics-recheck-20261027 | [report](reports/strata-metrics-recheck-20261027--README.md) | See index.json |
| strata-optimization-ab-20261021 | [report](reports/strata-optimization-ab-20261021--README.md) | [summary](measurements/strata-optimization-ab-20261021--summary.json) |
| strata-overnight-20261026 | [report](reports/strata-overnight-20261026--README.md) | [summary](measurements/strata-overnight-20261026--summary.json) |
| strata-paged-cache-20261029 | [report](reports/strata-paged-cache-20261029--README.md) | [summary](measurements/strata-paged-cache-20261029--summary.json) |
| strata-pr-campaign-20261027 | [report](reports/strata-pr-campaign-20261027--README.md) | [summary](measurements/strata-pr-campaign-20261027--summary.json) |
| strata-pr3277-ab-20261026 | [report](reports/strata-pr3277-ab-20261026--README.md) | [summary](measurements/strata-pr3277-ab-20261026--summary.json) |
| strata-pr3277-stock-ab-20261026 | [report](reports/strata-pr3277-stock-ab-20261026--README.md) | [summary](measurements/strata-pr3277-stock-ab-20261026--summary.json) |
| strata-prefill-final-20261021 | [report](reports/strata-prefill-final-20261021--README.md) | [summary](measurements/strata-prefill-final-20261021--summary.json) |
| strata-production-ab-20261026 | [report](reports/strata-production-ab-20261026--README.md) | [summary](measurements/strata-production-ab-20261026--summary.json) |
| strata-quant-behavior-20261023 | [report](reports/strata-quant-behavior-20261023--README.md) | See index.json |
| strata-swift-dflash-borrowing-20261023 | — | [summary](measurements/strata-swift-dflash-borrowing-20261023--summary.json) |
| strata-swift15-iq2xs-20261022 | [report](reports/strata-swift15-iq2xs-20261022--README.md) | See index.json |
| strata-vision-enable-20261021 | [report](reports/strata-vision-enable-20261021--README.md) | See index.json |
| swift-engine-ab-20261025 | [report](reports/swift-engine-ab-20261025--README.md) | [summary](measurements/swift-engine-ab-20261025--summary.json) |
| swift-five-20261025 | [report](reports/swift-five-20261025--README.md) | [summary](measurements/swift-five-20261025--summary.json) |
