#!/usr/bin/env bash
set -euo pipefail

TARGET="${TARGET:-/usr/local/bin/gitex}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but not found on PATH."
  exit 1
fi

sudo install -m 0755 "${SRC_DIR}/gitex-docker-wrapper.sh" "${TARGET}"

echo "Installed gitex wrapper to: ${TARGET}"
echo ""
echo "Try:"
echo "  gitex ."
echo "  gitex . -i"
echo ""
echo "To override image:"
echo "  GITEX_IMAGE=ghcr.io/zozaai/gitex:latest gitex ."
