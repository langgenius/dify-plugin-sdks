.PHONY: dev
dev:
	uv sync

.PHONY: format
format:
	uv run ruff format

.PHONY: lint
lint:
	uv run ruff check

.PHONY: check
check:
	uv lock --check
	uv run ruff format --check --diff
	uv run ruff check

.PHONY: test
test:
	uv run pytest tests -n 0

.PHONY: docs
docs:
	uv run python -m dify_plugin.cli generate-docs
	mkdir -p .mkdocs/docs
	mv docs.md .mkdocs/docs/schema.md

.PHONY: build
build:
	uv build --no-create-gitignore --no-sources

.PHONY: clean
clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf dist/ .pytest_cache/ .ruff_cache/
	rm -f docs.md langgenius-openai.difypkg
	uv run ruff clean
