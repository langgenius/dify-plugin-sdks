import base64
import hmac
from collections.abc import Generator
from copy import deepcopy
from inspect import signature
from io import BytesIO
from typing import Any

import pytest
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from werkzeug import Request, Response
from werkzeug.wsgi import FileWrapper

from dify_plugin.core.entities.plugin.request import (
    AgentActions,
    DatasourceActions,
    DynamicParameterActions,
    EndpointActions,
    ModelActions,
    OAuthActions,
    PluginInvokeType,
    ToolActions,
    TriggerActions,
)
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.entities.datasource import DatasourceMessage
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.entities.trigger import EventDispatch, Subscription
from dify_plugin.interfaces.tool import Tool
from dify_plugin.invocations.file import File
from dify_plugin.plugin import Plugin

from .plugin_fixtures import contract_plugin, contract_source, invoke

__all__ = ["contract_plugin", "contract_source"]

ACTIONS = {
    PluginInvokeType.Tool: ToolActions,
    PluginInvokeType.Model: ModelActions,
    PluginInvokeType.Agent: AgentActions,
    PluginInvokeType.Endpoint: EndpointActions,
    PluginInvokeType.OAuth: OAuthActions,
    PluginInvokeType.Datasource: DatasourceActions,
    PluginInvokeType.Trigger: TriggerActions,
    PluginInvokeType.DynamicParameter: DynamicParameterActions,
}


CREDENTIALS = {"api_key": "valid"}
SUBSCRIPTION = {
    "endpoint": "https://plugin.invalid/events",
    "expires_at": 100,
    "parameters": {"event": "echo"},
    "properties": {"external_id": "subscription"},
}


def raw_request(path: str, body: bytes = b"", method: str = "POST") -> str:
    return (
        f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n"
        f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
    ).encode().hex() + body.hex()


# Wire names and request fields follow daemon access_types/access.go and requests/.
CASES = [
    (
        "tool",
        "invoke_tool",
        {
            "provider": "contract",
            "tool": "echo",
            "tool_parameters": {"message": "hello"},
            "credential_type": "oauth2",
        },
        [
            {"type": "text", "message": {"text": "hello"}},
            {"type": "json", "message": {"json_object": {"echo": "hello"}}},
        ],
    ),
    ("tool", "validate_tool_credentials", {"provider": "contract"}, [{"result": True}]),
    (
        "tool",
        "get_tool_runtime_parameters",
        {"provider": "contract", "tool": "echo"},
        [
            {
                "parameters": [
                    {"name": "message", "type": "string", "required": True},
                    {"name": "wait_for_peer", "type": "boolean", "required": False},
                ]
            }
        ],
    ),
    (
        "agent_strategy",
        "invoke_agent_strategy",
        {
            "agent_strategy_provider": "contract_agents",
            "agent_strategy": "echo",
            "agent_strategy_params": {"message": "hello"},
        },
        [{"type": "text", "message": {"text": "hello"}}],
    ),
    (
        "endpoint",
        "invoke_endpoint",
        {
            "raw_http_request": raw_request("/echo/item", b"hello"),
            "settings": {"label": "setting"},
        },
        [{"status": 201, "result": b"hello".hex()}],
    ),
    (
        "oauth",
        "get_authorization_url",
        {
            "provider": "events",
            "redirect_uri": "https://plugin.invalid/callback",
            "system_credentials": {"client_id": "client"},
        },
        [
            {
                "authorization_url": "https://provider.invalid/authorize?redirect_uri=https%3A%2F%2Fplugin.invalid%2Fcallback&client_id=client"
            }
        ],
    ),
    (
        "oauth",
        "get_credentials",
        {
            "provider": "events",
            "redirect_uri": "https://plugin.invalid/callback",
            "system_credentials": {"client_id": "client"},
            "raw_http_request": raw_request("/callback?code=code", method="GET"),
        },
        [
            {
                "credentials": {
                    "access_token": "token-code",
                    "refresh_token": "refresh",
                },
                "expires_at": -1,
                "metadata": {},
            }
        ],
    ),
    (
        "oauth",
        "refresh_credentials",
        {
            "provider": "events",
            "redirect_uri": "https://plugin.invalid/callback",
            "system_credentials": {"client_id": "client"},
            "credentials": {"access_token": "old", "refresh_token": "refresh"},
        },
        [
            {
                "credentials": {
                    "access_token": "refreshed",
                    "refresh_token": "refresh",
                },
                "expires_at": -1,
            }
        ],
    ),
    (
        "oauth",
        "revoke_credentials",
        {
            "provider": "events",
            "system_credentials": {"client_id": "client"},
            "credentials": {"access_token": "token", "refresh_token": "refresh"},
        },
        [{"status": "revoked", "reason_code": None, "retryable": False}],
    ),
    (
        "datasource",
        "validate_datasource_credentials",
        {"provider": "website"},
        [{"result": True}],
    ),
    (
        "datasource",
        "invoke_website_datasource_get_crawl",
        {
            "provider": "website",
            "datasource": "echo",
            "datasource_parameters": {"url": "https://example.invalid/page"},
        },
        [
            {"result": {"status": "processing", "completed": 0}},
            {
                "result": {
                    "status": "completed",
                    "completed": 1,
                    "web_info_list": [
                        {
                            "source_url": "https://example.invalid/page",
                            "content": "page content",
                        }
                    ],
                },
            },
        ],
    ),
    (
        "datasource",
        "invoke_online_document_datasource_get_pages",
        {
            "provider": "documents",
            "datasource": "echo",
            "datasource_parameters": {"workspace": "selected", "limit": 0},
        },
        [
            {
                "result": [
                    {
                        "workspace_id": "workspace",
                        "pages": [{"page_id": "page", "page_name": "Example"}],
                    }
                ]
            }
        ],
    ),
    (
        "datasource",
        "invoke_online_document_datasource_get_page_content",
        {
            "provider": "documents",
            "datasource": "echo",
            "page": {"workspace_id": "workspace", "page_id": "page", "type": "page"},
        },
        [
            {
                "type": "variable",
                "message": {
                    "variable_name": "content",
                    "variable_value": "page content",
                },
            },
            {
                "type": "variable",
                "message": {"variable_name": "page_id", "variable_value": "page"},
            },
            {
                "type": "variable",
                "message": {
                    "variable_name": "workspace_id",
                    "variable_value": "workspace",
                },
            },
        ],
    ),
    (
        "datasource",
        "invoke_online_drive_browse_files",
        {
            "provider": "drive",
            "datasource": "echo",
            "request": {
                "bucket": "bucket",
                "prefix": "folder/",
                "max_keys": 20,
                "next_page_parameters": {},
            },
        },
        [
            {
                "result": [
                    {
                        "bucket": "bucket",
                        "files": [{"id": "file", "name": "example.txt"}],
                        "is_truncated": True,
                        "next_page_parameters": {"cursor": "next"},
                    }
                ]
            }
        ],
    ),
    (
        "datasource",
        "invoke_online_drive_download_file",
        {
            "provider": "drive",
            "datasource": "echo",
            "request": {"bucket": "bucket", "id": "file"},
        },
        [
            {
                "type": "blob",
                "message": {"blob": "ZGF0YQ=="},
                "meta": {"mime_type": "text/plain", "file_name": "example.txt"},
            },
        ],
    ),
    (
        "trigger",
        "invoke_trigger_event",
        {
            "provider": "events",
            "event": "echo",
            "subscription": SUBSCRIPTION,
            "raw_http_request": raw_request("/events", b'{"message":"hello"}'),
            "parameters": {"field": "message"},
            "payload": {"message": "hello"},
            "credential_type": "oauth2",
        },
        [
            {
                "variables": {
                    "payload": {"message": "hello"},
                    "parameters": {"field": "message"},
                    "body": '{"message":"hello"}',
                },
                "cancelled": False,
            }
        ],
    ),
    (
        "trigger",
        "validate_trigger_credentials",
        {"provider": "events"},
        [{"result": True}],
    ),
    (
        "trigger",
        "dispatch_trigger_event",
        {
            "provider": "events",
            "subscription": SUBSCRIPTION,
            "raw_http_request": raw_request(
                "/events", b'{"message":"hello","sender":"external-user"}'
            ),
            "credential_type": "oauth2",
        },
        [
            {
                "events": ["echo"],
                "payload": {"message": "hello", "sender": "external-user"},
                "user_id": "external-user",
            }
        ],
    ),
    (
        "trigger",
        "subscribe_trigger",
        {
            "provider": "events",
            "endpoint": "https://plugin.invalid/events",
            "parameters": {"event": "echo"},
            "credential_type": "api-key",
        },
        [
            {
                "subscription": {
                    **SUBSCRIPTION,
                    "properties": {
                        "external_id": "subscription",
                        "credential_type": "api-key",
                    },
                }
            }
        ],
    ),
    (
        "trigger",
        "unsubscribe_trigger",
        {
            "provider": "events",
            "subscription": SUBSCRIPTION,
            "credential_type": "api-key",
        },
        [{"subscription": {"success": True, "message": "subscription"}}],
    ),
    (
        "trigger",
        "refresh_trigger",
        {
            "provider": "events",
            "subscription": SUBSCRIPTION,
            "credential_type": "api-key",
        },
        [{"subscription": {**SUBSCRIPTION, "expires_at": 200}}],
    ),
    (
        "dynamic_parameter",
        "fetch_parameter_options",
        {
            "provider": "events",
            "provider_action": "provider",
            "parameter": "event",
            "credential_type": "api-key",
        },
        [{"options": [{"value": "echo", "label": {"en_US": "event"}}]}],
    ),
]

MODEL_CASES = [
    (
        "validate_provider_credentials",
        "llm",
        {},
        [{"result": True, "credentials": CREDENTIALS}],
    ),
    (
        "validate_model_credentials",
        "llm",
        {},
        [{"result": True, "credentials": CREDENTIALS}],
    ),
    (
        "invoke_llm",
        "llm",
        {
            "prompt_messages": [{"role": "user", "content": "hello"}],
            "model_parameters": {"temperature": 0.5},
            "tools": [
                {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object"},
                }
            ],
            "stop": ["END"],
            "stream": True,
        },
        [{"model": "echo", "delta": {"message": {"content": "hello"}}}],
    ),
    (
        "start_polling",
        "llm",
        {
            "prompt_messages": [{"role": "user", "content": "hello"}],
            "model_parameters": {"temperature": 0.5},
            "tools": [
                {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object"},
                }
            ],
            "stop": ["END"],
            "stream": False,
            "json_schema": {"type": "object"},
        },
        [
            {
                "status": "running",
                "plugin_state": {
                    "model": "echo",
                    "content": "hello",
                    "json_schema": {"type": "object"},
                },
            }
        ],
    ),
    (
        "check_polling",
        "llm",
        {"plugin_state": {"content": "hello"}},
        [
            {
                "status": "succeeded",
                "result": {"model": "echo", "message": {"content": "hello"}},
            }
        ],
    ),
    (
        "get_llm_num_tokens",
        "llm",
        {"prompt_messages": [{"role": "user", "content": "hello"}], "tools": []},
        [{"num_tokens": 5}],
    ),
    (
        "invoke_text_embedding",
        "text-embedding",
        {"texts": ["hello"], "input_type": "query"},
        [{"model": "echo", "embeddings": [[5.0]]}],
    ),
    (
        "invoke_multimodal_embedding",
        "text-embedding",
        {
            "documents": [{"content": "hello", "content_type": "text"}],
            "input_type": "query",
        },
        [{"model": "echo", "embeddings": [[5.0]]}],
    ),
    (
        "get_text_embedding_num_tokens",
        "text-embedding",
        {"texts": ["hello"]},
        [{"num_tokens": [5]}],
    ),
    (
        "invoke_rerank",
        "rerank",
        {
            "query": "search query",
            "docs": ["first document", "second document"],
            "score_threshold": 0.5,
            "top_n": 1,
        },
        [
            {
                "model": "echo",
                "docs": [{"index": 0, "text": "first document", "score": 0.9}],
            }
        ],
    ),
    (
        "invoke_multimodal_rerank",
        "rerank",
        {
            "query": {"content": "search query", "content_type": "text"},
            "docs": [{"content": "first document", "content_type": "text"}],
            "score_threshold": 0.5,
            "top_n": 1,
        },
        [
            {
                "model": "echo",
                "docs": [{"index": 0, "text": "first document", "score": 0.9}],
            }
        ],
    ),
    (
        "invoke_tts",
        "tts",
        {"content_text": "hello", "voice": "echo", "tenant_id": "tenant"},
        [{"result": b"hello".hex(), "mime_type": "audio/wav"}],
    ),
    (
        "get_tts_model_voices",
        "tts",
        {"language": "en_US"},
        [{"voices": [{"name": "Echo", "value": "echo"}]}],
    ),
    (
        "invoke_speech2text",
        "speech2text",
        {"file": b"hello".hex()},
        [{"result": "hello"}],
    ),
    ("invoke_moderation", "moderation", {"text": "blocked"}, [{"result": True}]),
    (
        "get_ai_model_schemas",
        "llm",
        {},
        [{"model_schema": {"model": "echo", "model_type": "llm"}}],
    ),
]

MODEL_METHODS = {
    "validate_model_credentials": "validate_credentials",
    "invoke_llm": "_invoke",
    "start_polling": "_start_polling",
    "check_polling": "_check_polling",
    "get_llm_num_tokens": "get_num_tokens",
    "invoke_text_embedding": "_invoke",
    "invoke_multimodal_embedding": "_invoke_multimodal",
    "get_text_embedding_num_tokens": "get_num_tokens",
    "invoke_rerank": "_invoke",
    "invoke_multimodal_rerank": "_invoke_multimodal",
    "invoke_tts": "_invoke",
    "get_tts_model_voices": "get_tts_model_voices",
    "invoke_speech2text": "_invoke",
    "invoke_moderation": "_invoke",
    "get_ai_model_schemas": "get_model_schema",
}
RUNTIME_METHODS = {
    "invoke_tool": ("get_tool_cls", "_invoke", "tool_parameters"),
    "get_tool_runtime_parameters": ("get_tool_cls", "_get_runtime_parameters", None),
    "invoke_agent_strategy": (
        "get_agent_strategy_cls",
        "_invoke",
        "agent_strategy_params",
    ),
    "invoke_website_datasource_get_crawl": (
        "get_website_crawl_datasource_cls",
        "_get_website_crawl",
        "datasource_parameters",
    ),
    "invoke_online_document_datasource_get_pages": (
        "get_online_document_datasource_cls",
        "_get_pages",
        "datasource_parameters",
    ),
    "invoke_online_document_datasource_get_page_content": (
        "get_online_document_datasource_cls",
        "_get_content",
        "page",
    ),
    "invoke_online_drive_browse_files": (
        "get_online_drive_datasource_cls",
        "_browse_files",
        "request",
    ),
    "invoke_online_drive_download_file": (
        "get_online_drive_datasource_cls",
        "_download_file",
        "request",
    ),
}
TRIGGER_METHODS = {
    "get_authorization_url": "_oauth_get_authorization_url",
    "get_credentials": "_oauth_get_credentials",
    "refresh_credentials": "_oauth_refresh_credentials",
    "revoke_credentials": "_oauth_revoke_credentials",
    "invoke_trigger_event": "_on_event",
    "validate_trigger_credentials": "_validate_api_key",
    "dispatch_trigger_event": "_dispatch_event",
    "subscribe_trigger": "_create_subscription",
    "unsubscribe_trigger": "_delete_subscription",
    "refresh_trigger": "_refresh_subscription",
    "fetch_parameter_options": "_fetch_parameter_options",
}
CASES += [
    (
        "model",
        action,
        {
            "provider": "contract_models",
            "model_type": model_type,
            "model": "echo",
            **payload,
        },
        expected,
    )
    for action, model_type, payload, expected in MODEL_CASES
]


def assert_contains(actual: object, expected: object) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), actual
        for key, value in expected.items():
            assert key in actual, actual
            assert_contains(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list), actual
        assert len(actual) == len(expected), actual
        for item, expected_item in zip(actual, expected, strict=True):
            assert_contains(item, expected_item)
    else:
        assert actual == expected


def test_every_public_action_has_one_route(contract_plugin: Plugin) -> None:
    assert set(ACTIONS) == set(PluginInvokeType)
    assert {(kind, action) for kind, action, _, _ in CASES} == {
        (kind.value, action.value)
        for kind, actions in ACTIONS.items()
        for action in actions
    }
    for invoke_type, actions in ACTIONS.items():
        for action in actions:
            request = {"type": invoke_type.value, "action": action.value}
            assert (
                sum(route.filter(request) for route in contract_plugin.routes) == 1
            ), request


@pytest.mark.parametrize(
    ("kind", "action", "payload", "expected"),
    CASES,
    ids=[f"{kind}.{action}" for kind, action, _, _ in CASES],
)
def test_public_actions_execute_registered_plugins(
    contract_plugin: Plugin,
    mocker: MockerFixture,
    kind: str,
    action: str,
    payload: dict,
    expected: list[dict],
) -> None:
    request = deepcopy({
        "type": kind,
        "action": action,
        "user_id": "user-1",
        "credentials": CREDENTIALS,
        **payload,
    })
    original = deepcopy(request)
    if action in MODEL_METHODS:
        model = contract_plugin.registration.get_model_instance(
            payload["provider"], ModelType(payload["model_type"])
        )
        method = MODEL_METHODS[action]
        parameters = signature(getattr(type(model), method))
        call = mocker.spy(type(model), method)
        forwarded = deepcopy(request)
        for key in ("type", "action", "provider", "model_type", "user_id"):
            forwarded.pop(key)
        if action.startswith("invoke_") or action in {"start_polling", "check_polling"}:
            forwarded["user"] = "user-1"
    elif action in RUNTIME_METHODS:
        getter, method, parameter = RUNTIME_METHODS[action]
        provider_cls = getattr(contract_plugin.registration, getter)(
            request.get("agent_strategy_provider", request.get("provider")),
            request.get(
                "tool", request.get("datasource", request.get("agent_strategy"))
            ),
        )
        parameters = signature(getattr(provider_cls, method))
        call = mocker.spy(provider_cls, method)
        forwarded = (
            {
                "parameters" if kind == "agent_strategy" else parameter: deepcopy(
                    request[parameter]
                )
            }
            if parameter is not None
            else {}
        )
    elif action in TRIGGER_METHODS:
        factory = contract_plugin.registration.trigger_factory
        if action == "invoke_trigger_event":
            _, provider_cls = factory.iter_events(request["provider"])[request["event"]]
        elif action == "dispatch_trigger_event":
            provider_cls = factory.get_provider_cls(request["provider"])
        else:
            provider_cls = factory.get_subscription_constructor_cls(request["provider"])
        method = TRIGGER_METHODS[action]
        parameters = signature(getattr(provider_cls, method))
        call = mocker.spy(provider_cls, method)
        forwarded = {
            name: deepcopy(request[name])
            for name in parameters.parameters
            if name not in {"self", "request"}
        }
    if action == "get_tool_runtime_parameters":
        with pytest.warns(DeprecationWarning, match="replaced by dynamic select"):
            messages = invoke(contract_plugin, request)
    else:
        messages = invoke(contract_plugin, request)
    assert len(messages) == len(expected), messages
    for message, fields in zip(messages, expected, strict=True):
        assert message["type"] == "stream", message
        assert message["data"]
        assert_contains(message["data"], fields)

    if (
        action in MODEL_METHODS
        or action in RUNTIME_METHODS
        or action in TRIGGER_METHODS
    ):
        call.assert_called_once()
        received = parameters.bind(*call.call_args.args, **call.call_args.kwargs)
        provider = received.arguments.pop("self")
        if action in RUNTIME_METHODS:
            assert provider.runtime.user_id == original["user_id"]
            if kind != "agent_strategy":
                assert provider.runtime.credentials == original["credentials"]
                assert provider.runtime.session_id == "session-1"
            if kind == "tool":
                assert provider.runtime.credential_type.value == original.get(
                    "credential_type", "api-key"
                )
            assert provider.session.session_id == "session-1"
        elif action in TRIGGER_METHODS:
            if kind != "oauth":
                assert provider.runtime.credentials == original["credentials"]
                assert provider.runtime.credential_type.value == original.get(
                    "credential_type", "api-key"
                )
            assert provider.runtime.session.session_id == "session-1"
            if action == "invoke_trigger_event":
                assert (
                    provider.runtime.subscription.model_dump()
                    == original["subscription"]
                )
            if "request" in received.arguments:
                http_request = received.arguments.pop("request")
                assert (
                    http_request.get_data()
                    == bytes.fromhex(original["raw_http_request"]).split(
                        b"\r\n\r\n", 1
                    )[1]
                )
        if action == "invoke_speech2text":
            assert received.arguments.pop("file").closed
            forwarded.pop("file")
        actual = TypeAdapter(dict[str, Any]).dump_python(
            received.arguments, mode="json", exclude_unset=True
        )
        assert actual == forwarded


def test_tool_runtime_parameters_reach_the_plugin(contract_plugin: Plugin) -> None:
    # Dify's ToolClient.get_runtime_parameters consumes this daemon action.
    request = {
        "type": "tool",
        "action": "get_tool_runtime_parameters",
        "user_id": "user-1",
        "provider": "contract",
        "tool": "echo",
        "credentials": {"api_key": "valid"},
    }
    with pytest.warns(DeprecationWarning, match="replaced by dynamic select"):
        messages = invoke(contract_plugin, request)
    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    parameters = messages[0]["data"]["parameters"]
    assert len(parameters) == 2
    assert parameters[0]["name"] == "message"
    assert parameters[0]["type"] == "string"
    assert parameters[0]["required"] is True


def request_for(action: str, **overrides: object) -> dict:
    kind, _, payload, _ = next(case for case in CASES if case[1] == action)
    return deepcopy({
        "type": kind,
        "action": action,
        "user_id": "user-1",
        "credentials": CREDENTIALS,
        **payload,
        **overrides,
    })


@pytest.mark.parametrize("action", [case[1] for case in CASES])
def test_invalid_action_payload_reports_one_error_and_ends(
    contract_plugin: Plugin, action: str
) -> None:
    request = request_for(action)
    required_field = "raw_http_request" if action == "invoke_endpoint" else "user_id"
    del request[required_field]

    messages = invoke(contract_plugin, request)

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert messages[0]["data"]["error_type"] == "ValidationError"
    assert required_field in messages[0]["data"]["message"]


@pytest.mark.parametrize("action", [case[1] for case in CASES if case[0] != "endpoint"])
def test_missing_provider_reports_one_error_and_ends(
    contract_plugin: Plugin, action: str
) -> None:
    field = (
        "agent_strategy_provider" if action == "invoke_agent_strategy" else "provider"
    )
    messages = invoke(
        contract_plugin, request_for(action, **{field: "missing-provider"})
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert messages[0]["data"]["error_type"] in {"ValueError", "TypeError"}
    assert "missing-provider" in messages[0]["data"]["message"]


@pytest.mark.parametrize(
    "action",
    [
        "validate_tool_credentials",
        "validate_provider_credentials",
        "validate_model_credentials",
        "validate_datasource_credentials",
        "validate_trigger_credentials",
    ],
)
def test_invalid_credentials_preserve_plugin_failure(
    contract_plugin: Plugin, action: str
) -> None:
    messages = invoke(
        contract_plugin, request_for(action, credentials={"api_key": "invalid"})
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert messages[0]["data"]["error_type"] == "ValueError"
    assert messages[0]["data"]["message"] == "invalid credentials"


@pytest.mark.parametrize(
    ("action", "field"),
    [
        ("invoke_tool", "tool"),
        ("get_tool_runtime_parameters", "tool"),
        ("invoke_agent_strategy", "agent_strategy"),
        ("invoke_website_datasource_get_crawl", "datasource"),
        ("invoke_online_document_datasource_get_pages", "datasource"),
        ("invoke_online_drive_browse_files", "datasource"),
        ("invoke_trigger_event", "event"),
    ],
)
def test_missing_implementation_reports_the_requested_name(
    contract_plugin: Plugin, action: str, field: str
) -> None:
    messages = invoke(contract_plugin, request_for(action, **{field: "missing-action"}))

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert "missing-action" in messages[0]["data"]["message"]


@pytest.mark.parametrize("size", [0, 1, 8191, 8192, 8193, 16384, 4 * 1024 * 1024])
def test_blob_chunk_boundaries_round_trip(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    content = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
    metadata = {"mime_type": "application/octet-stream", "filename": "result.bin"}

    def invoke_blob(tool: Tool, parameters: dict) -> Generator[ToolInvokeMessage]:
        del parameters
        yield tool.create_blob_message(content, meta=metadata)

    plugin_cls = contract_plugin.registration.get_tool_cls("contract", "echo")
    monkeypatch.setattr(plugin_cls, "_invoke", invoke_blob)
    messages = invoke(contract_plugin, request_for("invoke_tool"))

    assert len(messages) == (size + 8191) // 8192 + 1
    chunks = [message["data"]["message"] for message in messages]
    assert all(message["type"] == "stream" for message in messages)
    assert all(message["data"]["type"] == "blob_chunk" for message in messages)
    assert all(message["data"]["meta"] == metadata for message in messages)
    assert len({chunk["id"] for chunk in chunks}) == 1
    assert len(chunks[0]["id"]) == 32
    assert [chunk["sequence"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk["total_length"] == size for chunk in chunks)
    assert [chunk["end"] for chunk in chunks] == [False] * (len(chunks) - 1) + [True]
    assert not chunks[-1]["blob"]
    assert b"".join(base64.b64decode(chunk["blob"]) for chunk in chunks) == content
    # The daemon rejects JSON lines over 5 MiB before Dify sees the message.
    assert all(len(chunk["blob"]) <= 4 * ((8192 + 2) // 3) for chunk in chunks)


def test_tool_blob_subclasses_keep_the_base_chunk_contract(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TaggedMessage(ToolInvokeMessage):
        source: str

    def provider(*_args: object, **_kwargs: object) -> Generator[ToolInvokeMessage]:
        yield TaggedMessage(
            type=ToolInvokeMessage.MessageType.BLOB,
            message=ToolInvokeMessage.BlobMessage(blob=b"custom"),
            source="custom-tool",
        )

    plugin_cls = contract_plugin.registration.get_tool_cls("contract", "echo")
    monkeypatch.setattr(plugin_cls, "_invoke", provider)

    messages = invoke(contract_plugin, request_for("invoke_tool"))

    assert len(messages) == 2
    assert all(message["type"] == "stream" for message in messages)
    assert all(
        set(message["data"]) == {"type", "message", "meta"} for message in messages
    )
    assert all(message["data"]["type"] == "blob_chunk" for message in messages)
    assert base64.b64decode(messages[0]["data"]["message"]["blob"]) == b"custom"
    assert not messages[1]["data"]["message"]["blob"]
    assert messages[1]["data"]["message"]["end"] is True


def test_repeated_tool_blob_keeps_existing_id_replacement(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = ToolInvokeMessage(
        type=ToolInvokeMessage.MessageType.BLOB,
        message=ToolInvokeMessage.BlobMessage(blob=b"payload"),
    )

    def provider(*_args: object, **_kwargs: object) -> Generator[ToolInvokeMessage]:
        yield original
        yield original

    plugin_cls = contract_plugin.registration.get_tool_cls("contract", "echo")
    monkeypatch.setattr(plugin_cls, "_invoke", provider)

    messages = invoke(contract_plugin, request_for("invoke_tool"))

    assert len(messages) == 4
    chunks = [message["data"]["message"] for message in messages]
    assert base64.b64decode(chunks[0]["blob"]) == b"payload"
    assert base64.b64decode(chunks[2]["blob"]) == chunks[0]["id"].encode()
    assert [chunk["total_length"] for chunk in chunks] == [7, 7, 32, 32]
    assert [chunk["end"] for chunk in chunks] == [False, True, False, True]
    assert original.message.blob == chunks[2]["id"].encode()


@pytest.mark.parametrize("kind", ["drive", "document", "agent"])
@pytest.mark.parametrize(
    ("size", "metadata"),
    [
        (0, None),
        (4, {"file_name": "result.txt"}),
        (4 * 1024 * 1024, {"mime_type": "application/octet-stream"}),
        (4, {"file_name": "image.png", "mime_type": "image/png"}),
    ],
    ids=["empty", "named", "large", "image"],
)
def test_datasource_and_agent_blobs_preserve_wire_format_without_uploads(
    contract_plugin: Plugin,
    mocker: MockerFixture,
    kind: str,
    size: int,
    metadata: dict | None,
) -> None:
    content = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
    upload = mocker.patch.object(File, "upload")
    message_type = AgentInvokeMessage if kind == "agent" else DatasourceMessage
    original = message_type(
        type=message_type.MessageType.BLOB,
        message=message_type.BlobMessage(blob=content),
        meta=metadata,
    )
    expected = original.model_dump(mode="json")
    finalized = []

    def provider(*_args: object, **_kwargs: object) -> Generator:
        try:
            yield original
        finally:
            finalized.append(True)

    if kind == "drive":
        plugin_cls = contract_plugin.registration.get_online_drive_datasource_cls(
            "drive", "echo"
        )
        method, action = "_download_file", "invoke_online_drive_download_file"
    elif kind == "document":
        plugin_cls = contract_plugin.registration.get_online_document_datasource_cls(
            "documents", "echo"
        )
        method, action = (
            "_get_content",
            "invoke_online_document_datasource_get_page_content",
        )
    else:
        plugin_cls = contract_plugin.registration.get_agent_strategy_cls(
            "contract_agents", "echo"
        )
        method, action = "_invoke", "invoke_agent_strategy"
    mocker.patch.object(plugin_cls, method, provider)

    messages = invoke(contract_plugin, request_for(action))

    assert messages == [{"type": "stream", "data": expected}]
    assert messages[0]["data"]["type"] == "blob"
    assert base64.b64decode(messages[0]["data"]["message"]["blob"]) == content
    upload.assert_not_called()
    assert finalized == [True]


def test_partial_tool_stream_preserves_data_then_reports_failure(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch
) -> None:
    finalized = []

    def fail(tool: Tool, parameters: dict) -> Generator[ToolInvokeMessage]:
        del parameters
        try:
            yield tool.create_text_message("first")
            message = "stream interrupted"
            raise ValueError(message)
        finally:
            finalized.append(True)

    tool_cls = contract_plugin.registration.get_tool_cls("contract", "echo")
    monkeypatch.setattr(tool_cls, "_invoke", fail)
    messages = invoke(contract_plugin, request_for("invoke_tool"))

    assert [message["type"] for message in messages] == ["stream", "error"]
    assert messages[0]["data"]["message"] == {"text": "first"}
    assert messages[1]["data"]["message"] == "stream interrupted"
    assert finalized == [True]


def test_endpoint_response_includes_route_values_and_settings(
    contract_plugin: Plugin,
) -> None:
    messages = invoke(contract_plugin, request_for("invoke_endpoint"))

    assert messages[0]["data"]["headers"]["X-Item"] == "item"
    assert messages[0]["data"]["headers"]["X-Setting"] == "setting"


@pytest.mark.parametrize("path", ["/missing", "/echo/item"])
def test_endpoint_missing_path_or_method_returns_http_404(
    contract_plugin: Plugin, path: str
) -> None:
    messages = invoke(
        contract_plugin,
        request_for(
            "invoke_endpoint", raw_http_request=raw_request(path, method="GET")
        ),
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    assert messages[0]["data"]["status"] == 404
    assert b"Failed to dispatch endpoint request" in bytes.fromhex(
        messages[0]["data"]["result"]
    )


def test_endpoint_exception_returns_http_500(contract_plugin: Plugin) -> None:
    messages = invoke(contract_plugin, request_for("invoke_endpoint", settings={}))

    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    assert messages[0]["data"]["status"] == 500
    assert b"Internal Server Error" in bytes.fromhex(messages[0]["data"]["result"])


def test_endpoint_stream_emits_headers_before_utf8_and_binary_chunks(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint_cls = next(contract_plugin.registration.endpoints.iter_rules()).endpoint

    def response(*args: object) -> Response:
        del args

        def chunks() -> Generator[str | bytes]:
            yield "你好"
            yield b"\x00\xff"

        return Response(chunks(), status=206, headers={"X-Test": "stream"})

    monkeypatch.setattr(endpoint_cls, "_invoke", response)
    messages = invoke(contract_plugin, request_for("invoke_endpoint"))

    assert len(messages) == 3
    assert all(message["type"] == "stream" for message in messages)
    assert messages[0]["data"]["status"] == 206
    assert messages[0]["data"]["headers"]["X-Test"] == "stream"
    assert "result" not in messages[0]["data"]
    assert bytes.fromhex(messages[1]["data"]["result"]).decode() == "你好"
    assert bytes.fromhex(messages[2]["data"]["result"]) == b"\x00\xff"


@pytest.mark.parametrize("credential_type", ["api-key", "oauth2", "unauthorized"])
def test_dynamic_tool_options_preserve_runtime_credential_type_and_identity(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch, credential_type: str
) -> None:
    runtimes = []

    def options(tool: Tool, parameter: str) -> list[ParameterOption]:
        runtimes.append(tool.runtime)
        return [
            ParameterOption(
                value=tool.runtime.credential_type.value,
                label=I18nObject(en_us=parameter),
            )
        ]

    tool_cls = contract_plugin.registration.get_tool_cls("contract", "echo")
    monkeypatch.setattr(tool_cls, "_fetch_parameter_options", options)
    messages = invoke(
        contract_plugin,
        request_for(
            "fetch_parameter_options",
            provider="contract",
            provider_action="echo",
            credential_type=credential_type,
        ),
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    assert_contains(
        messages[0]["data"],
        {"options": [{"value": "api-key", "label": {"en_US": "event"}}]},
    )
    assert len(runtimes) == 1
    assert runtimes[0].credentials == CREDENTIALS
    assert runtimes[0].user_id == "user-1"
    assert runtimes[0].session_id == "session-1"


def test_dynamic_event_options_dispatch_to_the_event(
    contract_plugin: Plugin, mocker: MockerFixture
) -> None:
    _, event_cls = contract_plugin.registration.trigger_factory.iter_events("events")[
        "echo"
    ]
    call = mocker.spy(event_cls, "_fetch_parameter_options")
    messages = invoke(
        contract_plugin,
        request_for(
            "fetch_parameter_options", provider_action="echo", credential_type="oauth2"
        ),
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    assert_contains(
        messages[0]["data"],
        {"options": [{"value": "echo", "label": {"en_US": "event"}}]},
    )
    call.assert_called_once()
    runtime = call.call_args.args[0].runtime
    assert runtime.credentials == CREDENTIALS
    assert runtime.credential_type.value == "oauth2"
    assert runtime.session.session_id == "session-1"


def test_unknown_dynamic_action_returns_an_error(contract_plugin: Plugin) -> None:
    messages = invoke(
        contract_plugin,
        request_for("fetch_parameter_options", provider_action="missing"),
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert (
        messages[0]["data"]["message"]
        == "Cannot find the target to fetch parameter options"
    )


@pytest.mark.parametrize("provider", ["contract", "website"])
def test_oauth_selects_tool_and_datasource_providers(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    registration = contract_plugin.registration
    schema = registration.trigger_factory.get_configuration(
        "events"
    ).subscription_constructor.oauth_schema
    if provider == "contract":
        configuration, provider_cls, _ = registration.tools_mapping[provider]
    else:
        mapping = registration.datasource_mapping[provider]
        configuration, provider_cls = mapping.configuration, mapping.provider_cls
    configuration.oauth_schema = schema

    def authorization_url(
        self: object, redirect_uri: str, system_credentials: dict
    ) -> str:
        assert isinstance(self, provider_cls)
        assert system_credentials == {"client_id": "client"}
        return redirect_uri + "?provider=" + provider

    monkeypatch.setattr(provider_cls, "_oauth_get_authorization_url", authorization_url)
    messages = invoke(
        contract_plugin, request_for("get_authorization_url", provider=provider)
    )

    assert messages == [
        {
            "type": "stream",
            "data": {
                "authorization_url": "https://plugin.invalid/callback?provider="
                + provider
            },
        }
    ]


def test_trigger_ignore_is_a_cancelled_result(contract_plugin: Plugin) -> None:
    messages = invoke(
        contract_plugin,
        request_for("invoke_trigger_event", parameters={"ignore": True}),
    )

    assert messages == [
        {"type": "stream", "data": {"variables": {}, "cancelled": True}}
    ]


@pytest.mark.parametrize("framing", ["content-length", "decoded-chunked"])
@pytest.mark.parametrize(
    ("content_type", "body", "expected"),
    [
        (
            "application/x-www-form-urlencoded",
            b"payload=%7B%22message%22%3A%22caf%C3%A9%22%7D&tag=one&tag=two&empty=&plus=a%2Bb",
            {
                "payload": ['{"message":"café"}'],
                "tag": ["one", "two"],
                "empty": [""],
                "plus": ["a+b"],
            },
        ),
        (
            "application/json",
            b'{\n  "message": "caf\\u00e9", "id": 9007199254740993\n}',
            {"message": "café", "id": 9007199254740993},
        ),
    ],
    ids=["form", "json"],
)
def test_webhook_dispatch_preserves_signed_body_and_request_fields(
    contract_plugin: Plugin,
    monkeypatch: pytest.MonkeyPatch,
    framing: str,
    content_type: str,
    body: bytes,
    expected: dict,
) -> None:
    signature = hmac.digest(b"webhook-secret", body, "sha256").hex()
    framing_header = (
        f"Content-Length: {len(body)}"
        if framing == "content-length"
        else "Transfer-Encoding: chunked"
    )
    # Dify serializes get_data() after HTTP transfer decoding, retaining headers.
    raw = (
        "POST /events/你好?state=a%2Bb&tag=one&tag=two HTTP/1.1\r\n"
        "Host: plugin.invalid\r\n"
        f"Content-Type: {content_type}\r\n{framing_header}\r\n"
        f"X-Webhook-Signature: {signature}\r\n\r\n"
    ).encode() + body
    provider_cls = contract_plugin.registration.trigger_factory.get_provider_cls(
        "events"
    )

    def dispatch(
        _self: object, subscription: Subscription, request: Request
    ) -> EventDispatch:
        assert subscription.endpoint == SUBSCRIPTION["endpoint"]
        assert request.method == "POST"
        assert request.path == "/events/你好"
        assert request.query_string == b"state=a%2Bb&tag=one&tag=two"
        assert request.args.to_dict(flat=False) == {
            "state": ["a+b"],
            "tag": ["one", "two"],
        }
        raw_body = request.get_data(cache=True)
        assert raw_body == body
        assert hmac.compare_digest(
            request.headers["X-Webhook-Signature"],
            hmac.digest(b"webhook-secret", raw_body, "sha256").hex(),
        )
        payload = (
            request.get_json()
            if content_type == "application/json"
            else request.form.to_dict(flat=False)
        )
        assert payload == expected
        return EventDispatch(
            events=["echo"], response=Response("accepted", status=202), payload=payload
        )

    monkeypatch.setattr(provider_cls, "_dispatch_event", dispatch)
    messages = invoke(
        contract_plugin,
        request_for("dispatch_trigger_event", raw_http_request=raw.hex()),
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    assert messages[0]["data"]["events"] == ["echo"]
    assert messages[0]["data"]["payload"] == expected
    response = bytes.fromhex(messages[0]["data"]["response"])
    head, response_body = response.split(b"\r\n\r\n", 1)
    assert head.startswith(b"HTTP/1.1 202 ")
    assert response_body == b"accepted"


@pytest.mark.parametrize("file_body", [False, True])
def test_trigger_dispatch_closes_response_resources(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch, file_body: bool
) -> None:
    resource = BytesIO(b"accepted")
    response = Response(
        FileWrapper(resource) if file_body else resource.getvalue(), status=202
    )
    if not file_body:
        response.call_on_close(resource.close)
    provider_cls = contract_plugin.registration.trigger_factory.get_provider_cls(
        "events"
    )
    monkeypatch.setattr(
        provider_cls,
        "_dispatch_event",
        lambda *_args, **_kwargs: EventDispatch(events=["echo"], response=response),
    )

    try:
        messages = invoke(contract_plugin, request_for("dispatch_trigger_event"))

        assert len(messages) == 1
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["events"] == ["echo"]
        raw = bytes.fromhex(messages[0]["data"]["response"])
        assert raw.startswith(b"HTTP/1.1 202 ")
        assert raw.split(b"\r\n\r\n", 1)[1] == b"accepted"
        assert resource.closed
    finally:
        response.close()
        resource.close()


@pytest.mark.parametrize(
    "action",
    [
        "invoke_endpoint",
        "get_credentials",
        "invoke_trigger_event",
        "dispatch_trigger_event",
    ],
)
def test_invalid_http_encoding_reports_an_error(
    contract_plugin: Plugin, action: str
) -> None:
    messages = invoke(contract_plugin, request_for(action, raw_http_request="not-hex!"))

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert messages[0]["data"]["error_type"] == "Error"
    assert "Non-hexadecimal" in messages[0]["data"]["message"]


def test_llm_non_streaming_result_preserves_message(contract_plugin: Plugin) -> None:
    messages = invoke(contract_plugin, request_for("invoke_llm", stream=False))

    assert len(messages) == 1
    assert messages[0]["type"] == "stream"
    assert_contains(
        messages[0]["data"],
        {
            "model": "echo",
            "delta": {"message": {"role": "assistant", "content": "hello"}},
        },
    )


@pytest.mark.parametrize("provider", ["contract", "website"])
def test_registered_provider_without_oauth_reports_unsupported(
    contract_plugin: Plugin, provider: str
) -> None:
    registration = contract_plugin.registration
    if provider == "contract":
        registration.tools_mapping[provider][0].oauth_schema = None
    else:
        registration.datasource_mapping[provider].configuration.oauth_schema = None
    messages = invoke(
        contract_plugin, request_for("get_authorization_url", provider=provider)
    )

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert (
        messages[0]["data"]["message"]
        == f"Provider `{provider}` does not support OAuth"
    )


def test_tool_without_runtime_parameters_reports_unsupported(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool_cls = contract_plugin.registration.get_tool_cls("contract", "echo")
    monkeypatch.delattr(tool_cls, "_get_runtime_parameters")

    messages = invoke(contract_plugin, request_for("get_tool_runtime_parameters"))

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert (
        messages[0]["data"]["message"]
        == "Tool `echo` does not implement runtime parameters"
    )


@pytest.mark.parametrize("action", ["start_polling", "check_polling"])
def test_model_without_polling_reports_unsupported_before_invocation(
    contract_plugin: Plugin, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    model = contract_plugin.registration.get_model_instance(
        "contract_models", ModelType.LLM
    )
    monkeypatch.delattr(type(model), "_start_polling")

    messages = invoke(contract_plugin, request_for(action))

    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert "does not support polling" in messages[0]["data"]["message"]
