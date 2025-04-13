#!/bin/bash

## This scripts require PDM installed.
set -ex
set -o pipefail

SCRIPT_DIR="$(dirname "$0")"
PYTHON_SDK_DIR="$(dirname "${SCRIPT_DIR}")"

function main {
    cd "${PYTHON_SDK_DIR}"
    pdm install --group lint --group test
}

main
