# RTX 2080 workspace

The `rtx2080` branch is the production branch. **`profile.json` is the source of truth for serving settings.** `manage.py` expands its portable paths into the ignored `runtime/current.json` at every start. Credentials are read from `runtime/service.env`; they are never part of the public profile. `manage.py status` shows the selected branch, routing, guard and live health; `manage.py show` prints the resolved configuration without the API key.

## Everyday commands

Run from the repository root:

```sh
python rtx2080/manage.py status
python rtx2080/manage.py show
systemctl --user restart strata-serve.service
python rtx2080/manage.py check
python rtx2080/manage.py bench
```

Edit `rtx2080/profile.json`, then restart the service. Do not edit generated `runtime/current.json`. There is no separate production setting hidden in an old version checkout. The native binary is `runtime/bin/strata`; its currently tested hash and engine-source commit are in `CURRENT.json`. New builds do not replace it automatically.

## Current production

- Strata 0.2.9 / engine 0.1.55, CUDA SM75, RTX 2080 8 GB at 165 W, 64 GB system RAM.
- Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS, 125B MoE, NVMe weights.
- API model ID: `Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS`. Pi uses provider `strata` with this same ID, so T3 usage records identify the model and quant. Older requests using `local-model` remain accepted and receive the canonical model ID in responses. No extra alias is advertised.
- 131,072 context capacity; 32,768 GPU-resident INT8 KV tokens; KV prefetch.
- MTP spec4 / minimum probability 0.70; routing prior 1.5.
- 4,096 requested prefill chunk; 2,000 requested expert-cache slots, elastically resized.
- IQ1_M INT8 fused prefill enabled with the previous buffer layout; FP16 WMMA disabled.
- PCIe fraction 0.35; adaptation every step, 80 swaps, decay 0.97.
- 8 GiB / two-slot RAM session cache; minimum 1,024 tokens and park gain 1,024.
- One active decode request at a time; waiting requests queue. Cache slots are not parallel decode slots.
- CPU vision helper, three threads; authenticated API on port 8080; existing LAN access retained.
- Client-controlled sampling, normal thinking template, output fitted to available context; local loop closure enabled.

The November 1 validated update reads a cold 121K prompt at **866.2 tok/s**, versus 850.6 on the same-day previous production control (+1.8%). The usual 32K suite measured 889.2 tok/s, short chat decode 57.1 tok/s, and scored coding decode 62.16 tok/s. Both configurations passed 20/20 coding attempts and 4/4 near-capacity checks. [Full comparison, rejected alternatives and compact evidence](experiments/iq1m-current/README.md). The exact tested executable is installed; its hash and rollback record are in `CURRENT.json`.

The compact-layout / minimum16 follow-up was rolled back at the user’s request after reviewing its mixed performance. The exact pre-experiment binary and profile are restored; the previously validated IQ1_M fusion remains enabled. [Experimental results](experiments/iq1m-current/compact.md) are retained, and `CURRENT.json` records the rollback.

Pi token accounting uses the final Anthropic usage fields: total prompt tokens are
`input + cacheWrite + cacheRead`, and total usage adds `output`. Strata classifies
newly read prompt tokens mostly as cache writes; `input` alone is not the prompt
size. Cached reads count toward logical context usage, not newly processed prefill.
The local model has zero API pricing in Pi, while token counts remain recorded.
T3 prefers the response model name, which is why the serving profile and Pi use
the same canonical ID. Historical `local-model` usage is left unchanged because
that alias has served different models.

## What is local and what is upstream

Our enabled changes relative to upstream release `c62d5e3`:

1. Exact Turing attention scorer, `STRATA_SCORES_TURING=2`: smaller 32-query / 128-thread tiles, same reduction order.
2. SM75 native-IQ fused-prefill extension, `STRATA_PF_FUSED_SM75_IQ=1`: smaller tiles to fit IQ codebooks in Turing shared memory.
3. Prefill VRAM loans: defer/release MTP, head and verifier allocations while reading a prompt, then restore them for generation; repeat loans at 8,192 unread tokens and above.
4. Hot session restore: move restored state into the native RAM cache without recopying its large KV buffers.
5. IQ1_M/Q2_0 fused-prefill adapter, `STRATA_PF_FUSED_IQ1_M=1`, with `STRATA_PF_FUSED_LEGACY_LAYOUT=1` to retain the old buffer allocation. This extends fusion to the three remaining layers in the current mixed weights; activation rounding can change outputs.
6. Local repeated-thinking closure (`reasoning_loop_recovery: close`): use upstream detection and budget-closure machinery to resume once within the original output cap. This is a mitigation, not proof that the model's underlying loop cause is fixed.

MTP, residency-biased routing, PCIe expert access, native RAM conversation caching, adaptive expert caching, elastic cache allocation, KV prefetch and the general SM75 performance switches are upstream features. Upstream defaults also enable route-tail skipping at rank 7+ and CPU prompt sharing below 1,024 tokens. Routing and tail skipping can change outputs.

Disabled: KVA approximate prefill, all-checkpoint persistence, plain-prompt mode, the compact all-fused buffer layout, FP16 grouped WMMA and the persistent prefix-page tier. The repaired FP16 implementation is present as opt-in experimental code, but is **not enabled in production**.

## Experiments without more top-level checkouts

The same Git repository holds these branches:

- `rtx2080`: current daily-use code and profile.
- `experiment/yukon-three-20261101`: [Yukon-inspired kernel experiments and measurements](https://github.com/riccardogiorato/Strata/blob/6a84dec06ef1c40e84dc83d46bcb54db4a4ed90b/rtx2080/experiments/yukon-three/README.md). Tested through 127,990-token agent prompts; retained as research, with no production promotion.
- `experiment/persistent-prefix-cache`: oMLX-inspired persistent serialized prefix pages. Cold-restart and evicted-history recovery improved in the recorded experiments; saving remains synchronous and costs time. This is not a full oMLX implementation. See that branch's `docs/PERSISTENT_PREFIX_PAGES.md` and benchmark record.
- `experiment/iq1m-fused-prefill`: original TensorFold-inspired IQ1_M adapter and PR #4642 history on its older base, preserved unchanged.
- `experiment/iq1m-current`: completed current-source integration and validation. The validated INT8/old-layout configuration is now merged into production; FP16 and compact-layout alternatives remain disabled.

- `experiment/compact-prefill`: compact-buffer and minimum16 CPU-sharing investigation. Rolled back from production; code and measurements remain available for research.

Before switching the serving checkout to an experimental branch, stop `strata-serve.service`. Experimental branches retain their tested older base versions; do not apply the production profile blindly. Follow the branch's own build/configuration documentation. Return with `git switch rtx2080` and restart the service. Use separate ignored build outputs; do not overwrite `runtime/bin/strata` for a test.

[Experiment index](experiments/README.md) contains 41 historical campaign records, measurements and patches, including unsuccessful candidates. Historical code snapshots are tags under `archive/2026-10-31/`; see `experiments/source-history.json`. The branches preserve source, not their old build directories. Raw local evidence and retired artifacts are retained privately under `runtime/archive/` and in the benchmark workspace; model weights, credentials and raw conversations are not pushed.

## Build and local prerequisites

A public clone contains code, the portable profile, tests and compact evidence. It does not contain model weights, packed assets, binaries, credentials or a Python environment.

1. Create `runtime/venv` with Python 3.14 and install `requirements.txt` (plus monitor dependencies if using the monitor).
2. Put model shards under `$HOME/models` matching `profile.json`, or set `STRATA_MODEL_ROOT` in the local environment file. Keep model licenses separate from this MIT code.
3. Prepare the compatible dense/tokenizer pack, MTP runtime pack and expert profile using the upstream pack/setup tools. Their expected layout is `runtime/assets/packs/swift15-iq2xs-gsq`, `runtime/assets/mtp/rt` and `runtime/assets/data/expert-profile.bin`. The existing machine's validated assets were migrated unchanged.
4. Build with `bash rtx2080/build.sh`. CUDA SM75 is explicit. CMake fetches pinned GGML `3cf03257` unless `STRATA_GGML_DIR` points to that checkout. The old machine's legacy dependency snapshot is retained under ignored `runtime/deps/`.
5. With the service stopped, deliberately install a validated build as `runtime/bin/strata`. Build the upstream CPU vision helper if using the vision block; the current machine retains its validated helper under `runtime/bin/strata-vision`.
6. Create `runtime/service.env` with `STRATA_API_KEY=<your chosen key>` and chmod it to 600. Do not commit it. Then `python rtx2080/manage.py install-service` and start the service.

The generated user unit lives in `runtime/strata-serve.service`. The helper waits for the existing 165 W system power-limit setup; it does not change the power limit itself. The service uses the existing public/LAN binding specified by the profile; choose a different host there if required.

## Cleanup record

The old version folders existed for release comparisons, temporary builds and rollback copies. Source changes were saved as Git tags/branches before cleanup. Unique local configs/logs were archived, runtime assets were migrated, and the live process was checked before removing redundant directories. `runtime/archive/` holds the machine-specific preservation/deletion manifests; `experiments/source-history.json` is their public code-history index.
