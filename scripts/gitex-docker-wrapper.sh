#!/usr/bin/env bash
set -euo pipefail

IMAGE="${GITEX_IMAGE:-ghcr.io/zozaai/gitex:latest}"

# If someone runs `gitex` outside a TTY (pipes), avoid -it
TTY_ARGS=()
if [ -t 0 ] && [ -t 1 ]; then
  TTY_ARGS=(-it)
fi

# Use current directory as the repo mount point
# This makes `gitex .` behave as expected.
docker run --rm "${TTY_ARGS[@]}" \
  -v "${PWD}:/work" \
  -w /work \
  "${IMAGE}" \
  "$@"
