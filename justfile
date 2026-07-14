dev:
    uv sync
    uv run prek install

format:
    uv run ruff format

lint:
    uv run ruff check

check:
    uv lock --check
    uv run ruff format --check --diff
    uv run ruff check

test:
    uv run pytest

docs:
    uv run python -m dify_plugin.cli generate-docs
    mkdir -p .mkdocs/docs
    mv docs.md .mkdocs/docs/schema.md

build:
    uv build --no-create-gitignore --no-sources

clean:
    find . -type d -name '__pycache__' -prune -exec rm -rf {} +
    rm -rf dist/ .pytest_cache/ .ruff_cache/
    rm -f docs.md langgenius-openai.difypkg
    uv run ruff clean
