# Contributing to Dify Plugin SDK

This guide reflects the repository's current local tooling and GitHub Actions
checks.

Use `just` for routine development. Direct
[`uv`](https://docs.astral.sh/uv/), `ruff`, `pytest`, and
[`prek`](https://prek.j178.dev/) usage is still fine when you need a targeted
command.

## Development Setup

### Requirements

- Python 3.12 or 3.13
- [`uv`](https://docs.astral.sh/uv/)
- [`just`](https://github.com/casey/just)
- `git`

The package declares `requires-python = ">=3.12"`. CI currently validates
Python 3.12 and 3.13.

### Bootstrap

```bash
just dev
# optional for interactive work
source .venv/bin/activate
```

`just dev` will:

- run `uv sync`
- install [`prek`](https://prek.j178.dev/) Git hooks

The repository uses [`uv`](https://docs.astral.sh/uv/) for dependency and
virtual environment management. The default development environment includes
`pytest`, `pytest-cov`, `pytest-mock`, `pytest-xprocess`, `ruff`, `ty`, and
[`prek`](https://prek.j178.dev/).

### Git Hooks

`just dev` installs [`prek`](https://prek.j178.dev/) hooks from
[`prek.toml`](prek.toml).

The current hook set includes:

- trailing whitespace and end-of-file cleanup
- large file, case conflict, symlink, merge conflict, and private key checks
- JSON, JSON5, TOML, YAML, and XML validation
- line ending normalization and BOM cleanup
- executable shebang checks
- local `just check`

Useful direct commands:

```bash
uv run prek install
uv run prek run -a
uv run prek list
uv run prek validate-config
```

Use `just` by default. For targeted work, direct tool usage is still fine:

```bash
uv run ruff check src/dify_plugin/path.py
uv run pytest tests/path/test_file.py -k keyword
uv run prek run -a
```

## Testing and Validation

Use these commands for normal development:

- `just fmt` (also `just format`): run `uv run ruff format`
- `just lint`: run `just fmt`, then `uv run ruff check --fix`
- `just check`: run `uv lock --check`, `ruff format --check --diff`, and `ruff check`
- `just test`: run the SDK, OpenAI, Google Cloud Storage, and Jina example tests
- `just build`: build source and wheel distributions
- `just docs`: generate schema documentation into `.mkdocs/docs/schema.md`
- `just clean`: remove local build, test, and lint artifacts

Notes:

- `just check` is the non-mutating validation entrypoint used by PR checks and Git hooks.
- Integration tests that need the Dify plugin CLI are skipped when the binary is unavailable.
- CI installs the CLI with [`scripts/setup-dify-plugin-cli.sh`](scripts/setup-dify-plugin-cli.sh) before running tests.
- If you change dependencies, refresh and commit [`uv.lock`](uv.lock) before opening a pull request.

Run `just check` for every change, plus `just test` for behavior changes, `just build` for packaging changes, and `just docs` for schema changes.

### CI Checks

Pull requests targeting `main` currently run these checks:

1. PR title validation with `amannn/action-semantic-pull-request`
2. `just check` on Python 3.12, including `uv.lock` freshness validation
3. `just test` on Python 3.12 and 3.13 through the reusable test workflow

The test workflow installs the Dify plugin CLI, runs `just dev`, and then runs `just test`.

Pushes to `main` also run the MkDocs workflow.
It runs `just docs` on Python 3.12 and deploys `.mkdocs` to GitHub Pages.

Keep local workflow aligned with those checks.
A green local `just check` plus `just test` is useful, but it is not a complete substitute for CI because CI also validates PR titles and a Python version matrix.

## Git Commits

This repository enforces
[Conventional Commits](https://www.conventionalcommits.org/) for commit
messages. The same format is required for pull request titles.

The PR title validator currently accepts these types:

- `feat`
- `fix`
- `docs`
- `style`
- `refactor`
- `perf`
- `test`
- `build`
- `ci`
- `chore`
- `revert`

Rules:

- use an optional scope when it improves clarity
- mark breaking changes with `!`
- keep branch names aligned with the same type and scope vocabulary
- remember that the pull request title becomes the squash merge commit message

Examples:

```text
feat(model): add polling result validation
fix(runtime): close sessions after stream errors
docs(contributing): clarify local validation
refactor(server)!: remove deprecated transport entrypoint
```

Branch name examples:

```text
feat/model-polling-validation
fix/runtime-session-cleanup
docs/contributing-guide
```

## Issues

Before you start implementation or open a new issue, search the existing open
and closed issues and pull requests to confirm the work is not already tracked
or in progress.

Rules:

- self-assign every issue you create or work on
- do not open duplicate issues or parallel pull requests for the same change
- if related work already exists, continue that discussion instead of starting a
  new thread
- if no issue exists for the change, create one before opening a pull request
- if GitHub presents an issue template or issue form, fill out every required
  field and keep the provided structure intact

## Pull Requests

Every pull request must be linked to an issue. Use a closing or reference
keyword such as `Closes #123`, `Fixes #123`, or `Refs #123` in the pull request
body.

Before you open a pull request:

- search existing pull requests again to confirm there is no duplicate review in
  progress
- self-assign the pull request
- make sure the change stays focused and reviewable
- run `just check` and `just test`
- also run `just build` when the change affects packaging, project metadata, or SDK distribution behavior

When you open a pull request:

- use a Conventional Commits title, and mark breaking changes with `!`, because
  the pull request title becomes the squash merge commit message
- link the related issue in the pull request body
- follow
  [`.github/pull_request_template.md`](.github/pull_request_template.md)
  exactly
- do not delete required headings or checklist items from the template; if a
  section is not applicable, say so explicitly
- add or update tests for behavior changes unless the change genuinely does not
  require them
- update contributor-facing or user-facing documentation when needed
- describe compatibility impact for changes that affect SDK APIs, plugin
  manifests, generated schema documentation, examples, or runtime behavior

## Maintainer Notes

Version updates are managed manually with [`uv`](https://docs.astral.sh/uv/)
`version`:

```bash
uv version --no-sync --bump patch
uv version --no-sync --bump minor
uv version --no-sync --bump major
```

Those commands update the package version in
[`pyproject.toml`](pyproject.toml). If the lock file also needs to reflect the
new root package version, refresh and commit [`uv.lock`](uv.lock) as part of
the version bump change.

Release tags use the `v` prefix and are intended to be created from `main`
after the version bump pull request has been merged. The pushed tag must match
`[project].version` in [`pyproject.toml`](pyproject.toml).

Pushing `vX.Y.Z` triggers the release workflow. It:

1. verifies the tag matches `pyproject.toml` and points to a commit reachable
   from `main`
2. runs tests before building release distributions
3. builds source and wheel distributions with `just build`
4. creates or updates a GitHub draft release
5. publishes the same build artifacts to TestPyPI
6. waits for approval on the `pypi` environment
7. publishes the same build artifacts to PyPI and publishes the GitHub draft
   release
