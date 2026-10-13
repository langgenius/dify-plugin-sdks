# SDK regression map

The suite covers resource fixes and preserves existing public behavior against SDK `main` at `86e81e72`.
The tests run normally, without `xfail`, skips or reduced coverage thresholds.

Run `just test` for the full suite or pass a test file to run one group.
Ordinary test failures still produce JUnit and coverage reports through `just coverage`, which exits unsuccessfully.
The JUnit report identifies each parameter combination.

| Area | Behavior under test | Regression tests |
| --- | --- | --- |
| Endpoint response ownership | Completion, provider failure and client disconnect close response callbacks and body files. | [test_endpoint_lifecycle.py](core/test_endpoint_lifecycle.py) |
| Trigger response ownership | Dispatch closes the serialized response and its callback resource or file wrapper. | `test_trigger_dispatch_closes_response_resources` in [test_plugin_routes.py](core/test_plugin_routes.py) |
| Model manifest reuse | Repeated validation preserves model glob configuration. | [test_provider_manifest.py](entities/models/test_provider_manifest.py) |
| Tool manifest reuse | Credentials survive repeated validation and retries after repairing a child file. | `test_tool_credentials_survive_revalidation_after_load_or_repair` in [test_manifest_loading.py](entities/test_manifest_loading.py) |
| YAML credential aliases | Repeated loads preserve existing name resolution for shared credential mappings. | [test_trigger.py](entities/test_trigger.py) |
| Boolean defaults | Agent, datasource, trigger and tool-selector defaults retain their established numeric serialization of booleans. | [test_manifest_loading.py](entities/test_manifest_loading.py), [test_datasource.py](entities/test_datasource.py), [test_trigger.py](entities/test_trigger.py), [test_tool_behavior.py](interfaces/tool/test_tool_behavior.py) |
| Agent accounting | String-only token counting, special-token handling, output-budget adjustment and shared usage accumulation retain existing behavior. | [test_agent_behavior.py](interfaces/agent/test_agent_behavior.py) |
| Embedding batches | Provider response order, accepted vector values and batching retain existing behavior. | [test_http_embedding_rerank.py](interfaces/model/openai_compatible/test_http_embedding_rerank.py) |
| Embedding credentials | Credential checks retain their established response acceptance. | `test_embedding_validates_credentials_over_http` in [test_http_embedding_rerank.py](interfaces/model/openai_compatible/test_http_embedding_rerank.py) |
| Rerank results | Every batch retains min/max normalization and existing threshold and input behavior. | [test_http_embedding_rerank.py](interfaces/model/openai_compatible/test_http_embedding_rerank.py) |
| SSE event parsing | Standard events preserve content alongside existing response encodings, raw JSON, custom delimiters and EOF behavior. | [test_http_llm.py](interfaces/model/openai_compatible/test_http_llm.py) |
| Tool schema token accounting | Integer, boolean and null enums work in fallback token estimation. | [test_model_configuration.py](interfaces/model/openai_compatible/test_model_configuration.py), [test_http_llm.py](interfaces/model/openai_compatible/test_http_llm.py) |
| Invalid model configuration | Invalid modes report the supplied value in a configuration error. | `test_invalid_custom_model_mode_reports_a_configuration_error` in [test_model_configuration.py](interfaces/model/openai_compatible/test_model_configuration.py) |
| Numeric model parameters | Boolean numeric values, required defaults and template overrides retain existing acceptance and values. | [test_llm_parameters.py](interfaces/model/test_llm_parameters.py) |
| Stop sequences | Regular-expression matching and empty stop-list behavior retain their established results. | [test_llm_stop_tokens.py](interfaces/model/test_llm_stop_tokens.py) |
| Structured inputs | Updates to prompts, model parameters and stop lists retain existing requests, including shared objects. | [test_llm_structured_output.py](interfaces/model/test_llm_structured_output.py) |
| Structured XML | Existing processor hooks, fence handling and stop sequences remain available. | [test_llm_structured_output.py](interfaces/model/test_llm_structured_output.py) |
| Serverless shutdown | Closing the reader wakes its waiting event loop and stops the launched HTTP service. | [test_serverless.py](servers/test_serverless.py) |
| TCP write cancellation | Cancelling a partial frame closes its connection immediately; the read loop restores the connection before later frames. | [test_tcp.py](servers/test_tcp.py) |
| Repeated HTTP headers | Repeated media types and cookies retain the last request header value. | [test_http_parser.py](utils/test_http_parser.py) |
| Datasource files | Datasource and agent blob frames pass through without automatic uploads; tool chunk framing is preserved. | [test_plugin_routes.py](core/test_plugin_routes.py) |
| Provider overrides | Existing four-argument response handlers and fallback usage accounting retain their behavior. | [test_http_llm.py](interfaces/model/openai_compatible/test_http_llm.py) |

Embedding tests retain the original response ordering, including responses with out-of-order index metadata.
Manifest reuse tests check successful reuse, repaired-input retries and observable output.
Structured-call and shared-object regressions retain the baseline's existing input updates and resulting provider requests.

Protocol evidence and test isolation limits are recorded in [README.md](README.md).
These regressions do not establish compatibility with a running Dify deployment or external model service.
