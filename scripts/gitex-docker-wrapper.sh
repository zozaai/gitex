#!/usr/bin/env bash
set -euo pipefail

IMAGE="${GITEX_IMAGE:-gitex:latest}"

# Detect whether caller requested verbose output (-v/--verbose)
WANTS_VERBOSE=0
WANTS_INTERACTIVE=0

for arg in "$@"; do
  case "$arg" in
    -v|--verbose) WANTS_VERBOSE=1 ;;
    -i|--interactive) WANTS_INTERACTIVE=1 ;;
  esac
done

# If user is in a real TTY, interactive UIs can work.
HAS_TTY=0
if [ -t 0 ] && [ -t 1 ]; then
  HAS_TTY=1
fi

# Decide if we should run with a TTY.
# - Textual needs a TTY when interactive.
# - Non-interactive can run without TTY so we can safely capture stdout.
TTY_ARGS=()
if [ "${HAS_TTY}" = "1" ] && [ "${WANTS_INTERACTIVE}" = "1" ]; then
  TTY_ARGS=(-it)
fi

UID_NUM="$(id -u)"
XDG_RUNTIME_DIR_HOST="${XDG_RUNTIME_DIR:-/run/user/${UID_NUM}}"

EXTRA_ENV=(
  -e "GITEX_DOCKER=1"
)

EXTRA_MOUNTS=()

# Wayland passthrough (optional, not required when wrapper copies on host,
# but harmless and useful for future)
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR_HOST}/${WAYLAND_DISPLAY}" ]; then
  EXTRA_ENV+=(
    -e "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}"
    -e "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR_HOST}"
  )
  EXTRA_MOUNTS+=(
    -v "${XDG_RUNTIME_DIR_HOST}:${XDG_RUNTIME_DIR_HOST}"
  )
fi

# X11 passthrough (optional)
if [ -n "${DISPLAY:-}" ] && [ -d /tmp/.X11-unix ]; then
  EXTRA_ENV+=(
    -e "DISPLAY=${DISPLAY}"
  )
  EXTRA_MOUNTS+=(
    -v /tmp/.X11-unix:/tmp/.X11-unix
  )
fi

# Host clipboard copy helper (cross-platform best effort)
host_copy_to_clipboard() {
  local input_file="$1"

  if command -v wl-copy >/dev/null 2>&1; then
    wl-copy < "${input_file}"
    return 0
  fi

  if command -v xclip >/dev/null 2>&1; then
    xclip -selection clipboard < "${input_file}"
    return 0
  fi

  if command -v xsel >/dev/null 2>&1; then
    xsel --clipboard --input < "${input_file}"
    return 0
  fi

  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "${input_file}"
    return 0
  fi

  if command -v clip.exe >/dev/null 2>&1; then
    clip.exe < "${input_file}"
    return 0
  fi

  return 1
}

# ---------- Execution ----------
# Strategy:
# - Always ask container to --emit final output to stdout.
# - If interactive TTY is required (Textual UI), we must keep stdout as a terminal.
#   That means we can't "pipe" stdout without breaking the UI.
#   In that case, we capture output by writing it to a temp file via a second run (non-interactive),
#   using the same args, after the interactive selection completes.
#
# This keeps the UX consistent:
# - user sees the TUI,
# - then wrapper copies final output to host clipboard,
# - and prints only if -v was requested.

TMP_OUT="$(mktemp -t gitex_out.XXXXXX)"
cleanup() { rm -f "${TMP_OUT}"; }
trap cleanup EXIT

if [ "${WANTS_INTERACTIVE}" = "1" ] && [ "${HAS_TTY}" = "1" ]; then
  # 1) Run interactive UI with TTY (do NOT capture, or UI breaks)
  docker run --rm "${TTY_ARGS[@]}" \
    -v "${PWD}:/work" \
    -w /work \
    "${EXTRA_ENV[@]}" \
    "${EXTRA_MOUNTS[@]}" \
    "${IMAGE}" \
    "$@"

  # 2) Re-run non-interactive to capture final output for clipboard
  #    (same args, but add --emit, and disable TTY)
  docker run --rm \
    -v "${PWD}:/work" \
    -w /work \
    "${EXTRA_ENV[@]}" \
    "${EXTRA_MOUNTS[@]}" \
    "${IMAGE}" \
    --emit \
    "$@" > "${TMP_OUT}"
else
  # Non-interactive: capture directly
  docker run --rm \
    -v "${PWD}:/work" \
    -w /work \
    "${EXTRA_ENV[@]}" \
    "${EXTRA_MOUNTS[@]}" \
    "${IMAGE}" \
    --emit \
    "$@" > "${TMP_OUT}"
fi

# Copy to host clipboard
if host_copy_to_clipboard "${TMP_OUT}"; then
  # Match gitex behavior: status goes to stderr
  echo "[Copied to clipboard]" >&2

  # Print only if -v/--verbose
  if [ "${WANTS_VERBOSE}" = "1" ]; then
    cat "${TMP_OUT}"
  fi
else
  echo "[Failed to copy to clipboard – install wl-clipboard/xclip/xsel (Linux), pbcopy (macOS), or clip.exe (Windows)]" >&2
  # Fallback matches native behavior: print output so user still gets it
  cat "${TMP_OUT}"
fi
