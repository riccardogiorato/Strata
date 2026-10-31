> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Borrowing-only default deployment — 2026-10-21

User-authorized deployment of the exact PR #3281 binary tested in
the final screen (`../strata-prefill-final-20261021/README.md`), not the combined
PCIe-retention build and not a v0.2.2 upgrade.

- Patched binary: `../strata-021/build-turing-pr3281/strata` relative to the repo root.
- SHA-256: `a4fc75455185e2cb49450e86eb85ee288381c9eb116c0670550aafcfb83836e0`.
- Base: v0.2.1 `90767252f420e25223c739d604145ad15911d48b`, existing exact Turing scorer patch.
- PR head: `cf14700f5da34901908f5d12fa0f3437bcc44708`.
- Active config: `recipes/strata-configs/strata-q20-gsq-021-tailnet.json`.
- Same managed `strata-serve.service`, port 8080, model ID, authentication,
  Q2_0 weights, MTP, 131072 context, 32768 resident KV, and 165 W cap.

The previous executable remains at `../strata-021/build-turing/strata`.
`previous-config.json` is its exact pre-deployment config; `installed-config.json`
records the new one. `manifest.json` pins both binary hashes. `validation.json`
records deployment status and smoke checks; a failed installation automatically
restores the previous config and starts the original service.

## Rollback

From the repository root:

```bash
bash experiments/strata-loans-default-20261021/rollback.sh
```

This restores the previous config and restarts the service. Allow about 30 seconds
for model loading, then check `/health` for `loaded: true`. The rollback does not
delete either executable, the custom patch, or benchmark evidence.

## Eventual upstream replacement

Keep both binaries until a released upstream version actually includes the
borrowing work and passes a matched 128K / 20K-and-122K comparison. PR merge status
alone is not proof of inclusion in a release. Do not overlay a new engine on either
pinned binary. Build/test separately, then update the service config deliberately.
No automatic update or merge watcher was installed.

## Upstream report

[Published benchmark comment](https://github.com/Niko1221/Strata/pull/3281#issuecomment-6316861059).
The submitted text is retained as `github-comment.md`. It reports both the strong
cold-prefill gains and the limits: flat sustained decode, slower cached follow-up
in one pair, and no demonstrated whole-agent speedup.
