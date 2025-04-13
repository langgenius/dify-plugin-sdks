#!/bin/bash

set -ex
set -o pipefail

SCRIPT_DIR="$(dirname "$0")"
PYTHON_SDK_DIR="$(dirname "${SCRIPT_DIR}")"

function main {
    cd "${PYTHON_SDK_DIR}"
    pdm run pytest tests
}

main
