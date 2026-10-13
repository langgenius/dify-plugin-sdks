# SDK tests

The suite exercises the synchronous SDK and its gevent runtime through public operations, local protocol services, and an installed SDK wheel.

## Run tests

```bash
uv sync --locked
# Prepare the tokenizer data once when the cache is empty.
uv run python -c 'import tiktoken; tiktoken.encoding_for_model("gpt2")'
just check
just test
just coverage
```

Use the test entrypoint for focused runs too:

```bash
just test tests/core/test_runtime.py -q
just test tests/interfaces/model -k 'structured or stream'
just test -m integration
```

`tests/__main__.py` applies gevent patches before importing pytest and its plugins.
Calling `pytest` directly can patch SSL too late and change the concurrency behavior under test.
CI runs Python 3.12 with coverage and Python 3.13 without coverage.
The process and socket fixtures are validated on Linux, matching CI.
The [regression map](regressions.md) links corrected behavior to the tests that protect it.
Do not treat passing coverage thresholds as a passing test suite.

## Pytest dependencies

| Dependency | Purpose in this suite |
| --- | --- |
| [pytest-httpserver](https://pytest-httpserver.readthedocs.io/en/latest/howto.html) | Serves real HTTP, TLS and streaming responses, replacing the handwritten server process and its configuration protocol. |
| [pytest-timeout](https://pypi.org/project/pytest-timeout/) | Bounds each test, including setup and teardown, to 60 seconds using signals on Linux. |
| [pytest-socket](https://pypi.org/project/pytest-socket/) | Rejects external socket connections in the pytest process; only `127.0.0.1` and `::1` are allowed. |
| [Hypothesis](https://hypothesis.readthedocs.io/en/latest/reference/integrations.html) | Generates binary payloads and UTF-8 SSE fragmentation patterns, preserving explicit empty and chunk-boundary examples. |
| [trustme](https://trustme.readthedocs.io/) | Generates temporary CA and localhost certificates for HTTPS tests without checked-in keys. |

The existing `pytest-mock` provides scoped mocks, and `pytest-cov` handles coverage collection, subprocess merging and report generation.
RESPX and pytest-httpx were considered, but request mocks would not exercise the socket, TLS, streaming, and cancellation cases these fixtures own.
pytest-subprocess would replace the real pipes and child lifetimes that the process tests verify.
pytest-xdist would duplicate session fixtures in each worker and require separate validation of subprocess coverage and shared gevent state; it is not enabled.
An isolated `pytest-randomly` run with seed `20261013` passed all 1,216 baseline tests; no persistent dependency was added without evidence of an ordering problem.
The reviewed mutation was applied in a temporary copy: discarding rerank inputs still passed the entire baseline suite, so model route tests now assert the arguments received by the real plugin implementation.
Equivalent changes to mapping access, YAML path construction and registration list updates exposed tests that constrained internal call order; those assertions have been removed.
Stream tests accept independent copies of response chunks and compare them with snapshots taken before invocation, so shared mutable objects cannot hide corrupted usage or metadata.
Temporary mutations confirm that the tests accept serialization under a lock and reject interleaved frames or altered usage counts.
Further mutations confirm that dispatch tests detect missing credentials and session context, CLI tests detect incorrect routing and error fields, and valid reordered embedding results must succeed.
Mutation testing does not require another permanent dependency for these focused experiments.
The socket guard does not sandbox child processes; process fixtures run the local contract plugin and CLI emulator.

## Coverage gates

`just coverage` merges parent and subprocess data and writes `reports/junit.xml`, `reports/coverage.json`, and `reports/coverage.xml`.
Ordinary test failures still produce coverage reports; the command exits unsuccessfully if tests or coverage gates fail.
Pytest-cov manages the default `.coverage` database and intermediate `.coverage.*` files.
Hypothesis keeps its default `.hypothesis/` cache so later runs can replay generated examples.
These generated paths are ignored; `.coveragerc` remains trackable.
[The gate](../scripts/check_coverage.py) evaluates statement and branch totals separately, without rounding a failing result up to the threshold.

| Scope | Lines | Branches |
| --- | ---: | ---: |
| Entire SDK | 85% | 75% |
| `core/runtime.py` and `core/server/` | 90% | 85% |
| OpenAI compatible models, file downloads, and file uploads | 90% | 85% |

Coverage traces gevent and starts automatically in subprocesses.
SDK `threading` workers are patched greenlets; enabling both the `thread` and `gevent` tracers loses executed events in this runtime.
The wheel fixture checks that coverage is active in each plugin process when the parent collects coverage.
Installed package paths are mapped back to `src/dify_plugin` before merging.
SIGTERM capture retains measurements when process fixtures terminate their child processes.
Subprocess tracing enables parallel collection automatically; report formatting uses the library defaults.
Review missing branches alongside the behavior assertions; a percentage alone does not verify a protocol contract.

## Test map

| Boundary | Tests | Main cases |
| --- | --- | --- |
| Daemon backwards invocation | [core/test_runtime.py](core/test_runtime.py) | Immediate responses, session/request correlation, interleaving, HTTP errors, heartbeats, missing end frames, cancellation, and subscription cleanup |
| Session context | [core/test_session_context.py](core/test_session_context.py) | Nested sessions, generator lifetime, error restoration, and concurrent isolation |
| TCP, stdio, and serverless | [servers/](servers/) | Fragmented frames, partial writes, UTF-8, EOF, registration retries, reconnect races, close, response errors, and idle expiry |
| Registration and dispatch | [core/test_plugin_routes.py](core/test_plugin_routes.py), [core/test_plugin_registration.py](core/test_plugin_registration.py), [core/test_plugin_initialization.py](core/test_plugin_initialization.py) | All 37 public actions, provider argument forwarding, signed webhook bytes, forms, JSON, invalid payloads, missing providers, manifests, source files, assets, and installation modes |
| HTTP model adapters | [interfaces/model/openai_compatible/](interfaces/model/openai_compatible/) | Actual HTTP requests, SSE fragmentation, tool calls, usage, embedding batches, reranking, audio, multipart uploads, timeouts, and early close |
| Model interfaces | [interfaces/model/](interfaces/model/) | Parameter validation, zero values, decimal prices, structured output, errors, polling, concurrent calls, and timing cleanup |
| Files | [file/](file/) | Empty and binary downloads, cache and retry, signed URLs, multipart fields, upload response validation, proxy, custom CA, and hostname checks |
| Tools, agents, datasources, and triggers | [interfaces/](interfaces/) | Public calls, credentials, OAuth, subscriptions, message conversion, and failures |
| Service invocations | [invocations/](invocations/) | Recorded wire payloads, stream aggregation, multimodal content, metadata, empty results, and storage acknowledgements |
| Entities and configuration | [entities/](entities/), [config/](config/) | Binary round trips, input reuse, expiry sentinels, environment precedence, validation, and serialization |
| Plugin processes | [integration/](integration/) | Installed wheel identity, concurrent stdio sessions, large payloads, malformed input, child exit, startup failure, and bounded cleanup |
| Documentation and CLI | [test_documentation_generator.py](test_documentation_generator.py), [test_cli.py](test_cli.py) | Nested schema fields, enums, file generation, and command errors |

## Protocol evidence

Fixtures are based on these source revisions so that wire expectations can be checked independently of the SDK serializer:

- Dify: [`7b69dea2c802e7798089021f5ec150c22fe899aa`](https://github.com/langgenius/dify/tree/7b69dea2c802e7798089021f5ec150c22fe899aa).
- Plugin daemon: [`635d262e8e93e34ffb948573327d8486b97a11a3`](https://github.com/langgenius/dify-plugin-daemon/tree/635d262e8e93e34ffb948573327d8486b97a11a3).
- Official plugins: [`de2b2517039a9851fb1f056f06474fbf142154b9`](https://github.com/langgenius/dify-official-plugins/tree/de2b2517039a9851fb1f056f06474fbf142154b9).

Additional test review uses Dify [`982c56b1fdd40fb8ce27259464d736744e7e1c83`](https://github.com/langgenius/dify/tree/982c56b1fdd40fb8ce27259464d736744e7e1c83) and official plugins [`e7db65b5cabcaca6c6abba3d437bf57bd73055d3`](https://github.com/langgenius/dify-official-plugins/tree/e7db65b5cabcaca6c6abba3d437bf57bd73055d3).
The review checks embedding output against Dify's positional cache association, boolean defaults against its form fields, and trigger inputs against real webhook handlers.
The embedding response test uses the valid JSON number `1e400` to detect overflow: SDK serialization changes the resulting infinity to `null`, which the daemon's numeric decoder accepts as zero.
Agent boolean defaults follow the [strategy parameter mapping](https://github.com/langgenius/dify/blob/982c56b1fdd40fb8ce27259464d736744e7e1c83/web/app/components/workflow/nodes/_base/components/agent-strategy.tsx#L125) into a [form field that requires a boolean](https://github.com/langgenius/dify/blob/982c56b1fdd40fb8ce27259464d736744e7e1c83/web/app/components/header/account-setting/model-provider-page/model-modal/Form.tsx#L402); serializing them as zero or one loses the selected default.
Webhook fixtures follow Dify's [decoded request serialization](https://github.com/langgenius/dify/blob/982c56b1fdd40fb8ce27259464d736744e7e1c83/api/core/plugin/utils/http_parser.py#L7), Twilio's [form handling](https://github.com/langgenius/dify-official-plugins/blob/e7db65b5cabcaca6c6abba3d437bf57bd73055d3/triggers/twilio_trigger/provider/twilio.py#L74), and Discord's [signature input](https://github.com/langgenius/dify-official-plugins/blob/e7db65b5cabcaca6c6abba3d437bf57bd73055d3/triggers/discord_trigger/provider/discord.py#L41).
The subsequent review checks current consumers in Dify [`6b9bb4c7e8aac7f7930a2d25d3f3ae9fb3f2a217`](https://github.com/langgenius/dify/tree/6b9bb4c7e8aac7f7930a2d25d3f3ae9fb3f2a217) and official plugins [`24d1b811877408af1b5dfc2bf1cd2a3ec17d91df`](https://github.com/langgenius/dify-official-plugins/tree/24d1b811877408af1b5dfc2bf1cd2a3ec17d91df).
Rerank assertions follow Jina's [unmodified relevance scores](https://github.com/langgenius/dify-official-plugins/blob/24d1b811877408af1b5dfc2bf1cd2a3ec17d91df/models/jina/models/rerank/rerank.py#L92) and Dify's [score threshold and document association](https://github.com/langgenius/dify/blob/6b9bb4c7e8aac7f7930a2d25d3f3ae9fb3f2a217/api/core/rag/rerank/rerank_model.py#L57).

| Contract | Source |
| --- | --- |
| Serverless backwards responses contain raw session JSON followed by blank lines; blank lines also serve as heartbeats | Daemon [writer](https://github.com/langgenius/dify-plugin-daemon/blob/635d262e8e93e34ffb948573327d8486b97a11a3/internal/core/io_tunnel/backwards_invocation/transaction/serverless_writer.go#L37) and [handler](https://github.com/langgenius/dify-plugin-daemon/blob/635d262e8e93e34ffb948573327d8486b97a11a3/internal/core/io_tunnel/backwards_invocation/transaction/serverless_handler.go#L37) |
| File uploads use multipart `file`, signed query parameters, and HTTP 201 | Dify [plugin upload endpoint](https://github.com/langgenius/dify/blob/7b69dea2c802e7798089021f5ec150c22fe899aa/api/controllers/files/plugin_file_upload.py#L82) |
| Uploaded images expose `preview_url` to plugins | Official [image extraction tool](https://github.com/langgenius/dify-official-plugins/blob/de2b2517039a9851fb1f056f06474fbf142154b9/tools/dify_extractor/tools/image_assets.py#L138) |
| Blob chunks are reconstructed across 8 KiB boundaries | Dify [chunk merger](https://github.com/langgenius/dify/blob/7b69dea2c802e7798089021f5ec150c22fe899aa/api/core/plugin/utils/chunk_merger.py#L25) |
| OAuth expiry is an integer and `-1` means no expiry | Daemon [OAuth entities](https://github.com/langgenius/dify-plugin-daemon/blob/635d262e8e93e34ffb948573327d8486b97a11a3/pkg/entities/oauth_entities/oauth.go) and Dify [credential refresh](https://github.com/langgenius/dify/blob/7b69dea2c802e7798089021f5ec150c22fe899aa/api/core/tools/tool_manager.py#L303) |
| CLI readiness, invocation responses, errors, and end messages use JSON envelopes | Daemon [run entities](https://github.com/langgenius/dify-plugin-daemon/blob/635d262e8e93e34ffb948573327d8486b97a11a3/cmd/commandline/run/entities.go) and [output handling](https://github.com/langgenius/dify-plugin-daemon/blob/635d262e8e93e34ffb948573327d8486b97a11a3/cmd/commandline/run/run.go) |

When changing one of these contracts, inspect the corresponding consumer and update the request and response assertions together.

Datasource document content and drive downloads upload blob bytes through `session.file.upload` and emit the existing `binary_link` or `image_link` message.
The referenced Dify datasource consumer already resolves these file links; no consumer change is required.
This path requires access to Dify's signed file-upload endpoint and inherits its upload policy and the SDK's 10-second upload timeout.
HTTP regressions verify empty, small, image and 4 MiB uploads, metadata, and failure propagation for both datasource actions.
Tool and agent blob frames preserve the empty terminal chunk, metadata and input object, and stay below the daemon's default 5 MiB line limit for a 4 MiB payload.
Initialization assets with no bytes emit no chunks because the daemon requires nonempty asset data.

Response handler dispatch preserves the four-argument override contract used by DeepSeek, GPUStack, Moonshot, OpenAI API Compatible, OpenRouter, StepFun and LiteLLM.
The base handlers read tool definitions from the prepared HTTP request when calculating missing usage, including definitions injected by a provider.
Server-reported zero counts are preserved and the base streaming handler rejects incomplete streams.
Providers that replace the base handlers retain their own parsing and accounting behavior.

Serverless idle expiry emits an error followed by an end frame, and client disconnect cancels the request's provider task.
Backwards-invocation idle time counts business responses, so blank heartbeat lines cannot keep a silent invocation alive forever.
Cancelling a partial TCP write closes that socket before propagating cancellation; reconnection runs in the read loop so it cannot delay the cancelled caller.
Rerank scores already in `[0, 1]` are preserved, while batches containing values outside that interval retain min/max normalization.
The response does not distinguish raw logits that happen to fall inside `[0, 1]`; those values are preserved too.
When TTS splits WAV output, the SDK validates and combines PCM frames into one WAV file before yielding it; this requires buffering that output.

## Fixtures and isolation

[The HTTP fixture](http_server.py) uses pytest-httpserver with a dynamic localhost port and captures method, path, headers, and body.
The server uses the suite's patched threads; its documented `thread_target` extension sets a 10 ms shutdown poll instead of the default 500 ms.
Teardown wakes delayed response bodies before stopping the server and checks recorded server errors.
It can emit real HTTP chunks, delayed bodies, error statuses, and HTTPS responses.
The session CA and generated localhost certificates live in memory, following the HTTP server's [HTTPS fixture guidance](https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server).
Python's server TLS API and the `SSL_CERT_FILE` test require paths; trustme creates temporary PEM files for those calls and deletes them on context exit, including failures.
No certificate or private key is checked in, and the private-key hook needs no exception.
Tests clear inherited proxy and CA settings and use an empty netrc; individual configuration tests set their own environment.

[The wheel fixture](integration/conftest.py) builds the working tree, installs it into a temporary package directory, and compares every package file with the source tree.
The plugin starts outside the checkout with `python -m main`, matching the daemon, and reports its imported SDK path and version.
Its manifest declares only tools and endpoints, a combination allowed by the daemon.
In-process routing tests use the broader fixture to exercise every SDK action; its combined manifest is not an installable daemon package.
`PYTHONUNBUFFERED` is removed so a missing stdout flush cannot be hidden.
Concurrent invocations synchronize at a barrier so a single worker fails the concurrency test.
Dependencies come from the locked test environment.
Subprocess fixtures enforce startup and shutdown deadlines.
The stdio fixture retains raw stdout and stderr in the pytest temporary directory.

Concurrent tests use events and collect worker results so that worker exceptions fail the test.
Tests assert cleanup before fixture teardown can conceal a leak.
Response and Serverless lifecycle regressions keep explicit references to the resources, assert closure, and then clean up in `finally` so failing tests cannot leak into later cases.
Strict markers, strict configuration, and strict xfail handling are enabled.
Resource leaks, unhandled worker exceptions, and unraisable exceptions fail the suite.

## Validation limits

`PluginRunner` tests execute [a local CLI protocol fixture](fixtures/plugin_cli.py).
The installed wheel tests execute the SDK's actual registration, routing, and stdio loop.
These tests do not deploy Dify, run the released Go CLI, or call external model providers.
Dependency installation and initial tokenizer cache preparation require network access.
Extended load tests and whole-service deployment shutdown require separate validation.
The Serverless tests launch the real local HTTP server and exercise reader closure; they do not simulate container termination.
