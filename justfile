dev:
    uv sync
    uv run prek install

fmt:
    uv run ruff format

format: fmt

lint: fmt
    uv run ruff check --fix

check:
    uv lock --check
    uv run ruff format --check --diff
    uv run ruff check

[positional-arguments]
test *args:
    uv run python -m tests "$@"

coverage:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run coverage erase
    test_status=0
    uv run coverage run -m tests --junitxml=reports/junit.xml || test_status=$?
    uv run coverage combine
    uv run coverage json -o reports/coverage.json
    uv run coverage xml -o reports/coverage.xml
    uv run python scripts/check_coverage.py reports/coverage.json
    exit "$test_status"

build:
    uv build --no-create-gitignore --no-sources

docs:
    uv run python -m dify_plugin.cli generate-docs
    mkdir -p .mkdocs/docs
    mv docs.md .mkdocs/docs/schema.md

clean:
    find . -type d -name '__pycache__' -prune -exec rm -rf {} +
    rm -rf dist/ .pytest_cache/ .ruff_cache/
    rm -f docs.md langgenius-openai.difypkg
    uv run ruff clean
