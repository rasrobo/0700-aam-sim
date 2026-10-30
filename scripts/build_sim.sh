#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Building thumpbox-sim Desktop Simulator ==="
cd "${REPO_ROOT}"

# Ensure upstream is present
if [ ! -d "${REPO_ROOT}/upstream/.git" ] && [ ! -f "${REPO_ROOT}/upstream/.git" ]; then
    echo "Submodule not initialized. Running fetch_upstream.sh..."
    sh "${REPO_ROOT}/scripts/fetch_upstream.sh"
fi

BUILD_DIR="${REPO_ROOT}/build"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

echo "Configuring CMake..."
cmake -DCMAKE_BUILD_TYPE=Release ..

echo "Building targets..."
cmake --build . -- -j"$(nproc 2>/dev/null || echo 2)"

echo "Running unit tests and scenario golden checks..."
ctest --output-on-failure

echo ""
echo "=== Build and Verification Complete! ==="
echo "To run interactive PTY simulator:"
echo "  ${BUILD_DIR}/thumpbox-sim --pty /tmp/thumpbox-tty"
echo ""
echo "To run headless scenario runner:"
echo "  ${BUILD_DIR}/thumpbox-sim --scenario ${REPO_ROOT}/tests/scenarios/pad_and_knob_flow.json --assert-golden ${REPO_ROOT}/tests/golden/pad_and_knob_flow.golden.json"
echo ""
