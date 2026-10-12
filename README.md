# Dify Plugin SDK

The Python SDK for building Dify plugins: tools, model providers, agent strategies, HTTP extensions, datasources, and triggers.

[Plugin development guide](https://docs.dify.ai/en/develop-plugin/getting-started/getting-started-dify-plugin) · [Schema reference](https://langgenius.github.io/dify-plugin-sdks/schema/) · [Examples](https://github.com/langgenius/dify-official-plugins) · [Releases](https://github.com/langgenius/dify-plugin-sdks/releases)

## Getting started

Python 3.12 or later is required.
Install the SDK in your plugin's Python environment:

```bash
python -m pip install dify-plugin
```

The package name is `dify-plugin`; Python imports use `dify_plugin`.
For a new plugin, use the [Dify Plugin CLI](https://docs.dify.ai/en/develop-plugin/getting-started/cli) to generate the project, then follow the guide to configure, run, and package it.

## Compatibility

Before SDK 1.0, minor releases may include breaking changes.
Constrain your SDK dependency to the minor version you have tested, and review the [release notes](https://github.com/langgenius/dify-plugin-sdks/releases) before upgrading.

These versions serve different purposes:

| Version | Purpose |
| --- | --- |
| `dify-plugin` dependency | SDK version used by your plugin, declared in `requirements.txt` or `pyproject.toml`. |
| `version` in `manifest.yaml` | Your plugin's release version. |
| `meta.version` in `manifest.yaml` | Manifest schema version, set by the CLI when generating a plugin. |
| `meta.minimum_dify_version` in `manifest.yaml` | Earliest Dify version your plugin supports. |

Set `meta.minimum_dify_version` for the features your plugin uses and test against that version.
Feature availability depends on the SDK, Dify, and the plugin daemon.
See the [manifest schema](https://langgenius.github.io/dify-plugin-sdks/schema/#manifest) for field definitions.

## SDK development

Install [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just).
You can install `just` with `uv tool install rust-just`.
Run these commands from this repository:

```bash
just dev       # Sync dependencies and install Git hooks
just fmt       # Format code
just lint      # Format code and apply lint fixes
just check     # Check the lockfile, formatting, and linting
just test      # Run SDK tests
just build     # Build source and wheel distributions
just docs      # Generate schema documentation
```

CI tests Python 3.12 and 3.13.
See [CONTRIBUTING.md](CONTRIBUTING.md) for setup details, integration test requirements, and contribution guidelines.

## License

[Apache License 2.0](LICENSE).
