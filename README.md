## Dify Plugin SDK

A SDK sets for building plugins for Dify, including the following languages:

- Python

Here is a short introduction to Dify Plugin: <https://docs.dify.ai/plugins/introduction>

## SDK Version Management

### Python SDK

Always follow the [Semantic Versioning](https://semver.org/) for the Python SDK, for more details, please refer to [Python SDK README](./python/README.md).

## Manifest Version Reference

For the manifest specification, we've introduced two versioning fields:

- `meta.version` - The version of the manifest specification, designed for backward compatibility. When installing an older plugin to a newer Dify, it's difficult to ensure breaking changes never occur, but at least Dify can detect them through this field. Once an unsupported version is detected, Dify will only use the supported parts of the plugin.
- `meta.minimum_dify_version` - The minimum version of Dify, designed for forward compatibility. When installing a newer plugin to an older Dify, many new features may not be available, but showing the minimum Dify version helps users understand how to upgrade.

### Meta.Version Reference

| Manifest Version | Description                                                                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.0.2            | As `ToolProviderType` now supports `mcp`, an elder implementation is going to broken when user selected a `mcp` tool in Dify, so we bump it to 0.0.2 to ensure Dify knows that `mcp` is disabled if meta.version under 0.0.2. |
| 0.0.1            | Initial release                                                                                                                                                                                                               |

### Meta.MinimumDifyVersion Reference

| Minimum Dify Version | SDK Version   | Description                             |
|----------------------| ------------- | --------------------------------------- |
| 1.2.0                | 0.2.0         | Support fetching application info       |
| 1.4.0                | 0.0.1-beta.49 | Support LLM multimodal output           |
| 1.4.0                | 0.3.1         | Support OAuth functionality for plugins |
| 1.5.1                | 0.4.0         | Support `dynamic-select` parameter type |
| 1.5.1                | 0.4.0         | Support LLM structured output           |
| 1.6.0                | 0.4.1         | Support `dark-icon` field in manifest |
| 1.7.0                | 0.4.2         | Support OAuth functionality for plugins |
