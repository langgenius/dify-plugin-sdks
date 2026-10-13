# Dify Plugin SDK

The Python SDK for building Dify plugins: tools, model providers, agent strategies, HTTP extensions, datasources, and triggers.

[Plugin development guide](https://docs.dify.ai/en/develop-plugin/getting-started/getting-started-dify-plugin) · [Schema reference](https://langgenius.github.io/dify-plugin-sdks/schema/) · [Releases](https://github.com/langgenius/dify-plugin-sdks/releases)

## Getting Started

Python 3.12 or later is required.
Install the SDK in your plugin's Python environment:

```bash
python -m pip install dify-plugin
```

The package name is `dify-plugin`; Python imports use `dify_plugin`.
For a new plugin, use the [Dify Plugin CLI](https://docs.dify.ai/en/develop-plugin/getting-started/cli) to generate the project, then follow the guide to configure, run, and package it.

## Development

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

### Runtime compatibility in the 0.11.0 development tree

Compatibility tests use `main` at `86e81e72` as the baseline for existing callers.
They preserve public signatures, provider override hooks, blocking LLM string results, model accounting, parameter acceptance and transport completion policies.
Rerank continues to normalize every response batch with min/max, including scores already in `[0, 1]`.
Embedding results retain the provider's response order, and multi-part WAV output retains its original bytes and streaming behavior.
Datasource and agent blobs retain their existing message format; tool blobs retain their existing chunk framing.
OAuth expiration conversion, manifest default types, regular-expression stop matching and file redirect errors also retain their established behavior.

Resource cleanup covers completed, failed and cancelled calls, including TCP partial writes and Serverless shutdown.
Existing updates to structured prompts, stop lists, blob messages and shared usage objects retain their original results.
See the [regression map](tests/regressions.md) for covered behavior.

## Production Plugin Examples

See [langgenius/dify-official-plugins](https://github.com/langgenius/dify-official-plugins) for production plugin implementations published and used by Dify.

## LLM Polling Support

Since SDK 0.9.0, model plugins can declare the `polling` feature and implement `_start_polling()` and `_check_polling()` to handle long-running provider jobs through separate requests.
Both methods return `LLMPollingResult` with one of three states:

- `running`: return `plugin_state` for the next check.
- `succeeded`: return the final LLM `result`.
- `failed`: return a terminal `error`.

## Version Management

SDK versions use `MAJOR.MINOR.PATCH`:

- Major: incompatible API or architectural changes.
- Minor: new features.
- Patch: bug fixes.

Before SDK 1.0, minor releases may include breaking changes.
Review the [release notes](https://github.com/langgenius/dify-plugin-sdks/releases) before upgrading.

### For SDK Users

Constrain your SDK dependency to the minor version you have tested while allowing patch updates.
For example, `dify-plugin~=0.10.2` allows patches in the 0.10 series.
Review and test a new minor release before updating the constraint.

## Manifest Version Reference

The SDK dependency version and your plugin's top-level `version` in `manifest.yaml` are separate from these compatibility fields:

- `meta.version`: the manifest schema version, used by Dify to determine supported plugin capabilities.
- `meta.minimum_dify_version`: the earliest Dify version your plugin supports.

Set `meta.minimum_dify_version` for the features your plugin uses and test against that version.
Feature availability depends on the SDK, Dify, and the plugin daemon.
See the [manifest schema](https://langgenius.github.io/dify-plugin-sdks/schema/#manifest) for field definitions.

### Meta.Version Reference

| Manifest Version | Description |
| --- | --- |
| 0.0.2 | Adds the `mcp` tool provider type; use this schema version for plugins that accept MCP tools. |
| 0.0.1 | Initial manifest specification. |

### Meta.MinimumDifyVersion Reference

Minimum versions apply to the listed features.

| Minimum Dify Version | SDK Version | Description |
| --- | --- | --- |
| 1.2.0 | 0.2.0 | Fetch application information. |
| 1.4.0 | 0.0.1-beta.49 | LLM multimodal output. |
| 1.4.0 | 0.3.1 | OAuth authorization URL and credential retrieval. |
| 1.5.1 | 0.4.0 | `dynamic-select` parameters. |
| 1.5.1 | 0.4.0 | LLM structured output. |
| 1.6.0 | 0.4.1 | `icon_dark` field in the manifest. |
| 1.7.0 | 0.4.2 | Tool OAuth. |
| 1.8.1 | 0.4.4 | Filename in `MultiModalPromptMessageContent`. |
| 1.9.0 | 0.5.0 | Datasource plugins. |
| 1.10.0 | 0.6.0 | Trigger plugins. |
| 1.11.0 | 0.7.0 | Multimodal reranking and embeddings. |
| 1.14.0 | 0.8.1 | Dependency and project structure cleanup. |
| 1.14.2 | 0.9.0 | LLM polling invocations. |
| 1.16.0 | 0.10.0 | Read `app_id` through `get_current_session()` during app LLM invocations. |
| 1.16.1 | 0.10.0 | `multiple: true` for tool `select` and `dynamic-select` parameters; requires plugin daemon 0.5.0 or later. |
| Pending | 0.11.0 (unreleased) | Tool parameter `reset_on_change` declarations; requires plugin daemon 0.6.11 or later and the pending [Dify integration](https://github.com/langgenius/dify/pull/43040). |
| Pending | 0.11.0 (unreleased) | Optional `OnlineDriveFile.remote_metadata`; requires plugin daemon 0.6.11 or later, with Dify browse and change-detection support still pending. |

## License

[Apache License 2.0](LICENSE).
