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

test:
    uv run pytest
    uv run --project examples/openai --locked --with-editable . --with pytest pytest examples/openai/tests
    uv run --project examples/google_cloud_storage --locked --with-editable . --with pytest pytest examples/google_cloud_storage/tests
    uv run --project examples/jina --locked --with-editable . --with pytest pytest examples/jina/tests

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
