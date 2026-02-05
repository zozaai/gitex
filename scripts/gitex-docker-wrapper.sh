#!/usr/bin/env bash
set -euo pipefail

IMAGE="${GITEX_IMAGE:-gitex:latest}"

TTY_ARGS=()
if [ -t 0 ] && [ -t 1 ]; then
  TTY_ARGS=(-it)
fi

UID_NUM="$(id -u)"
XDG_RUNTIME_DIR_HOST="${XDG_RUNTIME_DIR:-/run/user/${UID_NUM}}"

EXTRA_ENV=()
EXTRA_MOUNTS=()

# Wayland clipboard support
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR_HOST}/${WAYLAND_DISPLAY}" ]; then
  EXTRA_ENV+=(
    -e "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}"
    -e "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR_HOST}"
  )
  EXTRA_MOUNTS+=(
    -v "${XDG_RUNTIME_DIR_HOST}:${XDG_RUNTIME_DIR_HOST}"
  )
fi

docker run --rm "${TTY_ARGS[@]}" \
  -v "${PWD}:/work" \
  -w /work \
  "${EXTRA_ENV[@]}" \
  "${EXTRA_MOUNTS[@]}" \
  "${IMAGE}" \
  "$@"
