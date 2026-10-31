> Historical experiment record. Paths and commands below describe the original campaign; use [the current profile](../../profile.json) for production. Raw conversations, private runtime files and rebuildable binaries are not published.

# Vision enabled for Strata and Pi — 2026-10-21

Enabled the existing multimodal path on the default Q2_0 + PR3281 runtime.
The language model, borrowing flags, 131072 context and 32768 resident KV are
unchanged. The service now reports `images: true`; Pi's `strata/local-model`
capabilities now include both `text` and `image`.

The image encoder runs on CPU with three threads and a 768-token image budget,
preserving GPU capacity for the language model. It reuses the installed
`mmproj-Qwen3.8-Flash-Next-BF16.gguf` projector and the existing CPU reader copied
from the 0.1.43 installation into `../strata-021/build-vision-cpu/bin/strata-vision`.
This is not a newly built 0.2.1 vision reader; compatibility was tested through
the current server. Reader SHA-256 is recorded in `validation.json`.

## Verification

- Authenticated OpenAI image request: correctly read `ORCHID 7319`, red square
  on the left and blue circle on the right. Full request took 6.89 seconds.
- Fresh Pi process using the production Anthropic endpoint and its `read` tool:
  correctly read `Land or Water` and `HOW 8 OPEN-WEIGHT MODELS SEE EARTH` from
  an actual site-header screenshot. Image was not stripped as unsupported.
- Pi initially attempted an unavailable `lookup` tool, then recovered to `read`.
  Vision works; this does not fix unrelated agent tool-selection mistakes.
- Service remains authenticated and loaded at 128K context.

Start a fresh Pi session/T3 local-model thread to ensure the revised model
capability declaration is loaded. Existing sessions may retain the old text-only
metadata. Large full-page screenshots may lose fine text at the 768-token image
budget; use focused screenshots. No broad visual-reasoning accuracy benchmark
or text-throughput comparison was run here.

## Rollback

From the repository root:

```bash
bash experiments/strata-vision-enable-20261021/rollback.sh
```

This restores the borrowing-enabled, text-only server config and the prior Pi
model declaration, then restarts the service. It does not undo VRAM borrowing.
The Pi rollback snapshot can contain credentials and is owner-only and gitignored.

Evidence: `validation.json`, `image-response.json`, `pi-image.jsonl`, and the two
test PNG files. Image encoding consumes CPU time and RAM; it is not free inference.
