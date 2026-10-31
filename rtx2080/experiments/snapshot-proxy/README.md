# Archived whole-session snapshot proxy

This preserves the earlier successful branch-indexed SSD snapshot experiment and its tests in this fork. It is distinct from the newer `experiment/persistent-prefix-cache` branch, which deduplicates serialized pages. Neither is enabled by the production profile.

Only the import layout changed during consolidation: `session_cache.py` now lives beside its callers. Run the CPU/API regression checks from this directory with `python -m unittest discover -v`. Use `python launch_cached.py --help` for the original isolated launcher. Its model/server config and cache directory must be supplied explicitly, and it refuses to run alongside an existing GPU inference process. The proxy binds to loopback. Do not repoint the production service at it implicitly.

Historical GPU/API results and limits: [overnight campaign](../reports/strata-overnight-20261026--README.md). The consolidation reruns CPU/API tests, not the old GPU benchmark. Prefix selection is heuristic; native Strata validates actual token reuse. Saves are synchronous whole snapshots, with bounded retention—not a full oMLX cache.

Consolidation validation (2026-10-31): all 26 CPU/API regression tests passed after the import relocation.
