#!/usr/bin/env bash
set -euo pipefail

TARGET="${TARGET:-/usr/local/bin/gitex}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SRC_DIR}/.." && pwd)"

# Local image name the wrapper will use
LOCAL_IMAGE="${LOCAL_IMAGE:-gitex:latest}"

# Optional: remote image to pull if build is skipped/fails
REMOTE_IMAGE="${REMOTE_IMAGE:-ghcr.io/zozaai/gitex:latest}"

# If set to 1, skip local build and just pull+tag
SKIP_BUILD="${SKIP_BUILD:-0}"

need() { command -v "$1" >/dev/null 2>&1; }

if ! need docker; then
  echo "Docker is required but not found on PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon doesn't seem to be running or you don't have permission."
  echo "Try: sudo systemctl start docker  (or open Docker Desktop)"
  exit 1
fi

echo "==> Installing gitex (Docker-based)"
echo "    Local image:  ${LOCAL_IMAGE}"
echo "    Remote image: ${REMOTE_IMAGE}"
echo ""

# 1) Build local image (default)
if [ "${SKIP_BUILD}" = "0" ]; then
  echo "==> Building Docker image locally..."
  if docker build -t "${LOCAL_IMAGE}" "${REPO_DIR}"; then
    echo "==> Build complete: ${LOCAL_IMAGE}"
  else
    echo "!! Local build failed. Falling back to pulling remote image..."
    SKIP_BUILD="1"
  fi
fi

# 2) Fallback: pull remote image + tag as local
if [ "${SKIP_BUILD}" = "1" ]; then
  echo "==> Pulling: ${REMOTE_IMAGE}"
  docker pull "${REMOTE_IMAGE}"

  echo "==> Tagging as: ${LOCAL_IMAGE}"
  docker tag "${REMOTE_IMAGE}" "${LOCAL_IMAGE}"
fi

# 3) Install wrapper as a real command
echo "==> Installing wrapper to: ${TARGET}"
sudo install -m 0755 "${SRC_DIR}/gitex-docker-wrapper.sh" "${TARGET}"

echo ""
echo "✅ Done."
echo ""
echo "Try:"
echo "  gitex --version"
echo "  gitex ."
echo "  gitex . -i"
echo ""
echo "Notes:"
echo "  - To force pull instead of build:"
echo "      SKIP_BUILD=1 ./scripts/install-gitex-docker.sh"
echo "  - To use a different remote image:"
echo "      REMOTE_IMAGE=ghcr.io/zozaai/gitex:latest SKIP_BUILD=1 ./scripts/install-gitex-docker.sh"
