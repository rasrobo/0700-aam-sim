#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

UPSTREAM_URL="https://github.com/MusicTribeOpenSource/0700-AAM"
UPSTREAM_DIR="${REPO_ROOT}/upstream"
VERSION_FILE="${REPO_ROOT}/UPSTREAM_VERSION"

if [ ! -f "${VERSION_FILE}" ]; then
    echo "Error: ${VERSION_FILE} not found." >&2
    exit 1
fi

TARGET_COMMIT="$(tr -d '[:space:]' < "${VERSION_FILE}")"

if [ -d "${UPSTREAM_DIR}/.git" ]; then
    echo "Updating existing upstream repository at ${UPSTREAM_DIR}..."
    cd "${UPSTREAM_DIR}"
    git fetch origin
    git checkout "${TARGET_COMMIT}"
else
    echo "Cloning upstream from ${UPSTREAM_URL}..."
    git clone "${UPSTREAM_URL}" "${UPSTREAM_DIR}"
    cd "${UPSTREAM_DIR}"
    git checkout "${TARGET_COMMIT}"
fi

echo "Upstream is pinned to commit: $(git rev-parse HEAD)"
