#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
args=(-S "$ROOT" -B "$ROOT/build/sm75" -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 -DCMAKE_CUDA_FLAGS=--allow-unsupported-compiler -DSTRATA_BUILD_TESTS=ON -DSTRATA_BUILD_CONVERSATION_TESTS=ON)
if [[ -n "${STRATA_GGML_DIR:-}" ]]; then args+=(-DSTRATA_GGML_DIR="$STRATA_GGML_DIR"); fi
cmake "${args[@]}"
cmake --build "$ROOT/build/sm75" --target strata -j "${BUILD_JOBS:-4}"
printf 'Built %s\nServing binary remains runtime/bin/strata until explicitly replaced with the service stopped.\n' "$ROOT/build/sm75/strata"
