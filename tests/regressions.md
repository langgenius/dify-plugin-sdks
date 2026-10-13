# SDK regression map

The SDK fixes the defects below, with regression tests covering public results, reuse, failures and resource cleanup.
The tests run normally, without `xfail`, skips or reduced coverage thresholds.

Run `just test` for the full suite or pass a test file to run one group.
`just coverage` also writes JUnit and coverage reports when tests fail, then returns a failing exit status.
The JUnit report identifies each parameter combination.

| Area | Corrected behavior | Regression tests |
| --- | --- | --- |
| Endpoint response ownership | Completion, provider failure and client disconnect close response callbacks and body files. | [test_endpoint_lifecycle.py](core/test_endpoint_lifecycle.py) |
| Trigger response ownership | Dispatch closes the serialized response and its callback resource or file wrapper. | `test_trigger_dispatch_closes_response_resources` in [test_plugin_routes.py](core/test_plugin_routes.py) |
| Model manifest reuse | Repeated validation preserves model glob configuration. | [test_provider_manifest.py](entities/models/test_provider_manifest.py) |
| Tool manifest reuse | Credentials survive repeated validation and retries after repairing a child file. | `test_tool_credentials_survive_revalidation_after_load_or_repair` in [test_manifest_loading.py](entities/test_manifest_loading.py) |
| YAML credential aliases | Credential names remain distinct when their source mappings share a YAML alias. | `test_subscription_credentials_do_not_alias_shared_yaml_mapping` in [test_trigger.py](entities/test_trigger.py) |
| Boolean defaults | Agent, datasource, trigger and tool-selector defaults retain boolean values in serialization. | [test_manifest_loading.py](entities/test_manifest_loading.py), [test_datasource.py](entities/test_datasource.py), [test_trigger.py](entities/test_trigger.py), [test_tool_behavior.py](interfaces/tool/test_tool_behavior.py) |
| Agent token counting | Text blocks contribute to the estimate and literal special-token text is accepted. | [test_agent_behavior.py](interfaces/agent/test_agent_behavior.py) |
| Embedding batches | Invalid counts, indices and vectors fail before later batches; reordered results retain their input association. | [test_http_embedding_rerank.py](interfaces/model/openai_compatible/test_http_embedding_rerank.py) |
| Embedding credentials | Credential validation requires a response object containing the model. | `test_embedding_validates_credentials_over_http` in [test_http_embedding_rerank.py](interfaces/model/openai_compatible/test_http_embedding_rerank.py) |
| SSE event parsing | LF, CRLF and CR delimiters, comments, event fields and fragmented UTF-8 preserve content. | `test_stream_parses_standard_sse_events` in [test_http_llm.py](interfaces/model/openai_compatible/test_http_llm.py) |
| Tool schema token accounting | Integer, boolean and null enums work in fallback token estimation. | [test_model_configuration.py](interfaces/model/openai_compatible/test_model_configuration.py), [test_http_llm.py](interfaces/model/openai_compatible/test_http_llm.py) |
| Invalid model configuration | Invalid modes report the supplied value in a configuration error. | `test_invalid_custom_model_mode_reports_a_configuration_error` in [test_model_configuration.py](interfaces/model/openai_compatible/test_model_configuration.py) |
| Numeric model parameters | Numeric rules reject booleans and non-finite numbers, including invalid required defaults. | [test_llm_parameters.py](interfaces/model/test_llm_parameters.py) |
| Stop sequences | Literal stop strings truncate at the earliest match. | [test_llm_stop_tokens.py](interfaces/model/test_llm_stop_tokens.py) |
| Repeated structured calls | Reusing prompts and stop lists sends the same effective request. | `test_structured_invocations_can_reuse_prompts_and_stop_sequences` in [test_llm_structured_output.py](interfaces/model/test_llm_structured_output.py) |
| Structured XML | Code fences inside XML text, attributes, CDATA and comments survive; outer Markdown fences are removed. | `test_structured_xml_preserves_inner_content` in [test_llm_structured_output.py](interfaces/model/test_llm_structured_output.py) |
| Serverless shutdown | Closing the reader wakes its waiting event loop and stops the launched HTTP service. | [test_serverless.py](servers/test_serverless.py) |
| Repeated HTTP headers | Repeated media types and cookies survive request decoding. | [test_http_parser.py](utils/test_http_parser.py) |
| Datasource files | Blob content uploads through the existing file service and returns a link that current Dify consumers accept. | [test_plugin_routes.py](core/test_plugin_routes.py) |
| Provider overrides | Existing four-argument response handlers continue to work with base fallback usage accounting. | [test_http_llm.py](interfaces/model/openai_compatible/test_http_llm.py) |

The embedding index regression permits either correct association or explicit rejection before further batches; it does not require support for reordered output.
Manifest and parameter reuse tests check successful reuse, repaired-input retries and observable output, rather than requiring every caller-owned object to remain unchanged.
The structured-call regression checks that repeated invocations send the same effective request.

Protocol evidence and test isolation limits are recorded in [README.md](README.md).
These regressions do not establish compatibility with a running Dify deployment or external model service.
