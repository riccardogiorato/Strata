> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Custom Strata 0.2.7 production deployment — 2026-10-28

The user authorized promoting the tested custom v0.2.7 build with routing
enabled. The normal `strata-serve` service, `strata` CLI and `strata-mon` now
use `${WORKSPACE}/strata-027`.

## Installed configuration

- Upstream revision: `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d` (v0.2.7, engine 0.1.52).
- Exact benchmarked executable SHA-256: `70c55d28ce098e5ad91939dc87f081670bb8170c6f5f289444bae629a72555cf`.
- Binary and helper library were copied byte-for-byte; the tested source and local patches were preserved. No rebuild or model download.
- Config: `recipes/strata-configs/strata-swift15-iq2xs-gsq-027-tailnet.json`.
- `STRATA_ROUTE_PRIOR=1.5`, `STRATA_KVA=0`, matching the measured candidate.
- Existing model, 128K context, MTP, int8/32K-resident KV, PCIe fraction 0.35, fused Turing/native-IQ prefill, VRAM loans and RAM session cache retained.
- Existing CPU vision config, host/port and API authentication retained. The SSD session proxy remains a separate launcher.
- Python environment is the same environment used in the benchmark; `.venv314` links to the retained v0.2.3 installation. Keep that installation for both runtime dependencies and rollback.

## Validation

`validation.json` records successful authenticated generation, structured tool
calling and retrieval from a cold 19,463-token prompt. The retrieval returned the
correct marker with 857.6 prefill tok/s and 22.98 seconds full request time.
This is a deployment smoke check, not an additional paired performance claim.

Health confirms the model is loaded at 131,072-token capacity with API-key and
image support enabled. Unauthenticated model access returns 401. Live process
inspection confirms the new executable and every expected environment flag,
including routing 1.5. The CLI reports 0.2.7. GPU power remains 165 W.
Vision configuration was preserved; a new image-inference check was not run.

Prior full validation is retained in `../strata-metrics-recheck-20261027/`:
80/80 new scored agent tasks and 24/24 controlled long-context code checks
passed. Combining initial and repeated routing-on suites gives 29/30, versus
30/30 for the old production baseline. Routing changes expert selection; the
measured 25.9% agent decode gain does not establish universal quality parity.

## Rollback

```bash
bash experiments/strata-027-default-20261028/rollback.sh
```

This restores the previous service and CLI/monitor wrappers, reloads systemd,
and starts the retained v0.2.3 configuration. Its executable and config were
verified unchanged. Local rollback snapshots are in the ignored `private/`
directory. `install.py` also rolls back automatically if deployment validation
fails. `deployment.json` records provenance and backup hashes. No commit or
push was made.
