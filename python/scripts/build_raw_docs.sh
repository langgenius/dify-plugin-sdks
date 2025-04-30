#!/bin/bash

set -ex
set -o pipefail

SCRIPT_DIR="$(dirname "$0")"
PYTHON_SDK_DIR="$(dirname "${SCRIPT_DIR}")"

function main {
    cd "${PYTHON_SDK_DIR}"
    pdm run python dify_plugin/cli.py generate-docs
    mkdir -p docs
    mv docs.md docs/schema.md
}

main
