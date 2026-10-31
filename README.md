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

## Production Plugin Examples

See [langgenius/dify-official-plugins](https://github.com/langgenius/dify-official-plugins) for production plugin implementations published and used by Dify.

## OpenAI-Compatible Embeddings

Starting in SDK 0.11.0 (unreleased), `OAICompatEmbeddingModel` validates each response batch before sending the next request.
Each input must have one nonempty vector of finite numbers, with consistent dimensions across all batches.
Responses with `index` fields must cover every input in that batch exactly once using integer indices starting at zero; the SDK restores input order.
Responses without indices retain response order.
Malformed responses, including mixed index metadata, numeric strings, and booleans, raise an SDK invocation error.
This applies to plugins using the shared implementation, including GiteeAI and SiliconFlow.

## LLM Polling Support

Since SDK 0.9.0, model plugins can declare the `polling` feature and implement `_start_polling()` and `_check_polling()` to handle long-running provider jobs through separate requests.
Both methods return `LLMPollingResult` with one of three states:

- `running`: return `plugin_state` for the next check.
- `succeeded`: return the final LLM `result`.
- `failed`: return a terminal `error`.

## Blocking LLM Replay

In SDK 0.11.0 (unreleased), blocking `session.model.llm.invoke` and `session.model.llm_structured_output.invoke` calls preserve the last non-`None` `opaque_body` snapshot.
Empty objects, arrays, strings, zero, and false are valid snapshots; trailing chunks without a snapshot do not erase them.
String chunks are concatenated, while nonempty content arrays retain their blocks and metadata in order, including when mixed with strings.
Providers must assemble complete tool calls before emitting them, once per call, with nonempty IDs unique within the response.
Calls may arrive in separate batches or together; collectors preserve their order and the original argument strings, and reject missing or duplicate IDs.
Each usage update is a cumulative snapshot for the current model response; collectors retain the last non-`None` snapshot, including zero values, and Agents add usage across model responses.
Use `message.get_text_content()` when a consumer needs plain text, and retain the complete message when replaying a tool turn.
`AssistantPromptMessage.is_empty()` treats tool calls and any non-`None` snapshot as content.
`ToolPromptMessage.is_empty()` treats a tool call ID as content, including when the tool result is empty.
The invoking Agent/plugin, provider, daemon, and host must all preserve these fields for replay across tool turns.

## OpenAI-Compatible Completion Input

In SDK 0.11.0 (unreleased), the shared `OAICompatLargeLanguageModel` completion mode accepts text from the first prompt message.
Text content blocks are concatenated in order into one prompt string, including empty lists as an empty string.
Image, audio, video, or document blocks in that prompt raise an SDK invocation error before sending a request, including when mixed with text.
For multimodal input, use chat mode with a model that supports the input modality and message role.

## OpenAI-Compatible Usage Estimates

In SDK 0.11.0 (unreleased), streaming and non-streaming responses estimate missing usage fields with the same counters.
Provider counts, including zero, take precedence; a missing or null count is estimated independently.
Completion counts the text sent from the first prompt message, while chat counts the complete message history and the tool definitions sent with the request.
Output estimates include text and tool calls, including responses with no text content.
These local estimates use the SDK tokenizer and pricing configuration; they do not represent the provider's billing record.
The public `get_num_tokens()` budget for completion also counts only the first prompt message and any supplied tool definitions.

Provider overrides of `_handle_generate_response()`, `_handle_generate_stream_response()`, and `_create_final_llm_result_chunk()` must accept and forward the optional `tools` parameter in SDK 0.11.0.
Overrides of `_num_tokens_from_string()` must follow the SDK signature `(text, tools=None)`; the method does not take a model name.

## OpenAI-Compatible Streaming

In SDK 0.11.0 (unreleased), `OAICompatLargeLanguageModel` preserves SSE data alongside comments and unknown fields.
Responses marked `text/event-stream` ignore events without data; invalid JSON in `data` fields still raises an invocation error.
The parser handles LF, CRLF, and CR line endings within events, including with custom delimiters.
A single leading UTF-8 BOM is ignored for both default and custom delimiters.
Raw JSON objects, single-prefix multiline JSON, and final payloads without a blank-line terminator remain supported.
Explicit response charsets are respected; responses without a charset default to UTF-8.
Streams must include a non-null `finish_reason` for the selected choice or a `[DONE]` event.
EOF without either raises an invocation error instead of returning a successful final chunk with partial text or tool calls.

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

### HTTP Error Responses in SDK 0.11.0 (unreleased)

SDK-generated Serverless and Endpoint failures return HTTP 500 with the body `Internal Server Error`.
The original exception and traceback are logged on the plugin server.
Endpoint route failures return HTTP 404 with `Not Found`; exceptions from plugin construction or invocation, including `ValueError`, return HTTP 500.
Explicit HTTP responses returned by a plugin retain their status, headers, and body.
Update clients that parse exception text or treat a plugin's `ValueError` as a 404.

Protecting errors raised during Endpoint streaming also requires the [daemon HTTP error fix](https://github.com/langgenius/dify-plugin-daemon/issues/834) on every daemon node.
With that fix, a stream that fails after headers are sent is interrupted, so clients must handle response-body read errors.
Upgrade the daemon first, then rebuild and deploy plugins with the updated SDK.

## Agent Token Estimates

In SDK 0.11.0 (unreleased), agent token estimates include text blocks as well as string content and treat special-token spellings such as `<|endoftext|>` as ordinary text.
Message metadata and non-text payloads are excluded.
Counting previously ignored text can reduce the output budget in strategies that call `recalc_llm_max_tokens`, including Function Calling and ReAct.
The GPT-2 estimate remains approximate: budget adjustment retains a minimum of 16 output tokens and lets the provider decide whether the prompt fits.

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

## Literal Stop Sequences

Starting in SDK 0.11.0 (unreleased), `LargeLanguageModel.enforce_stop_tokens` stops at the earliest literal sequence, including punctuation and backslashes.
An empty stop list or no matching sequence returns the full input.
Callers that used regex patterns must supply literal stop strings: for example, replace `r"\."` with `"."` to stop at a period.
An empty string inside the stop list still matches at the start of the input.

## License

[Apache License 2.0](LICENSE).
