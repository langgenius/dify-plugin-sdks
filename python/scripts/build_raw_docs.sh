#!/bin/bash

set -ex
set -o pipefail

SCRIPT_DIR="$(dirname "$0")"
PYTHON_SDK_DIR="$(dirname "${SCRIPT_DIR}")"

function main {
    cd "${PYTHON_SDK_DIR}"
    pdm run python dify_plugin/cli.py generate-docs
    mkdir -p .mkdocs/docs
    mv docs.md .mkdocs/docs/schema.md
}

main
