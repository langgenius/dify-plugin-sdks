## Dify Plugin SDK

A SDK sets for building plugins for Dify, including the following languages:

- Python

Here is a short introduction to Dify Plugin: <https://docs.dify.ai/plugins/introduction>

## Community & Social

Follow project updates and release announcements on Twitter/X: [@promethurs](https://x.com/promethurs).

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

| Minimum Dify Version | SDK Version   | Description                                        |
| -------------------- | ------------- | -------------------------------------------------- |
| 1.2.0                | 0.2.0         | Support fetching application info                  |
| 1.4.0                | 0.0.1-beta.49 | Support LLM multimodal output                      |
| 1.4.0                | 0.3.1         | Support OAuth functionality for plugins            |
| 1.5.1                | 0.4.0         | Support `dynamic-select` parameter type            |
| 1.5.1                | 0.4.0         | Support LLM structured output                      |
| 1.6.0                | 0.4.1         | Support `dark-icon` field in manifest              |
| 1.7.0                | 0.4.2         | Support OAuth functionality for plugins            |
| 1.8.1                | 0.4.4         | Support filename in MultiModalPromptMessageContent |
| 1.9.0                | 0.5.0         | Support Datasource functionality for plugins       |
| 1.10.0               | 0.6.0         | Support Trigger functionality for plugins          |

## GameJAM Player

GameJAM Player is a lightweight browser-based experience designed to showcase rapid prototypes built during game jams. It emphasizes zero-install sharing, responsive controls, and telemetry hooks that map nicely onto Dify Plugin workflows for collecting playtest feedback.

**Highlights**
- `Drop-in hosting` – distribute a single HTML file that runs anywhere a modern browser exists.
- `Controller-agnostic controls` – supports touch, keyboard, and pointer input with simple helpers for remapping.
- `Jam-friendly scaffolding` – includes a timer, scoring primitive, and heads-up messaging so teams can focus on core mechanics.

**Try the demo:** open `python/examples/gamejam_player_demo/index.html` in any browser to launch the micro game bundled with this repository.
