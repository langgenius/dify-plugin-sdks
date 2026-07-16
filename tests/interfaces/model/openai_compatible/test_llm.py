from collections import UserDict
from collections.abc import Mapping
from http import HTTPStatus
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


class DuckJsonObject:
    def __init__(self) -> None:
        self.trace: list[str] = []

    def get(self, key: str, default: object = None) -> str:
        del key, default
        self.trace.append("get")
        return "chat.completion"

    def __contains__(self, key: object) -> bool:
        del key
        self.trace.append("contains")
        return True

    def __getitem__(self, key: str) -> str:
        del key
        self.trace.append("getitem")
        return "chat.completion"


class StatefulTruth:
    def __init__(self) -> None:
        self.calls = 0

    def __bool__(self) -> bool:
        self.calls += 1
        return self.calls == 1


@pytest.mark.parametrize(
    ("stream_mode_auth", "stream", "max_tokens"),
    [("not_use", False, 5), ("use", True, 10)],
)
def test_validate_credentials_passes_extra_headers(
    stream_mode_auth: str,
    stream: bool,
    max_tokens: int,
) -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = {"object": "chat.completion"}
    response.close.side_effect = RuntimeError("close failed")
    api_key = str(123)
    credentials = {
        "api_key": api_key,
        "endpoint_url": "https://example.com/v1",
        "extra_headers": {
            "Authorization": str(456),
            "Content-Type": "application/custom+json",
            "X-Api-Key": str(789),
        },
        "mode": "chat",
        "stream_mode_auth": stream_mode_auth,
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ) as post:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert post.call_args.kwargs["headers"] == {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/custom+json",
        "X-Api-Key": str(789),
    }
    assert post.call_args.kwargs.get("stream", False) is stream
    assert post.call_args.kwargs["json"]["max_tokens"] == max_tokens
    response.close.assert_called_once()


@pytest.mark.parametrize("extra_headers", [False, "", [], [("X-Api-Key", "value")]])
def test_validate_credentials_rejects_non_mapping_extra_headers(
    extra_headers: object,
) -> None:
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "extra_headers": extra_headers,
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        ) as post,
        pytest.raises(CredentialsValidateFailedError),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    post.assert_not_called()


def test_validate_credentials_wraps_unreadable_error_response() -> None:
    error = RuntimeError("broken body")
    response = MagicMock(status_code=HTTPStatus.BAD_REQUEST)
    type(response).text = PropertyMock(side_effect=error)
    response.close.side_effect = RuntimeError("close failed")
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": "use",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is error
    response.close.assert_called_once()


def test_validate_credentials_accepts_mapping_response() -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = UserDict({"object": "chat.completion"})
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)


def test_validate_credentials_wraps_lazy_mapping_errors() -> None:
    error_message = "lazy response failed"
    json_result = MagicMock(spec=Mapping)
    json_result.get.side_effect = RuntimeError(error_message)
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = json_result
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError, match=error_message),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)


def test_validate_credentials_preserves_prepared_credential_errors() -> None:
    sentinel = CredentialsValidateFailedError("prepared credentials failed")
    credentials = MagicMock()
    credentials.get.side_effect = sentinel

    with pytest.raises(CredentialsValidateFailedError) as exc_info:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_response_credential_errors() -> None:
    sentinel = CredentialsValidateFailedError("response failed")
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.side_effect = sentinel
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_mapping_membership_access() -> None:
    json_result = DuckJsonObject()
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = json_result
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert json_result.trace == ["get", "contains", "getitem"]


def test_validate_credentials_compares_status_once() -> None:
    status = MagicMock()
    status.__ne__.side_effect = [True, False]
    response = MagicMock(status_code=status, text="failed")
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": "use",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    status.__ne__.assert_called_once_with(HTTPStatus.OK)


def test_validate_credentials_preserves_failed_status_second_access() -> None:
    sentinel = CredentialsValidateFailedError("second status read failed")
    response = MagicMock(text="failed")
    type(response).status_code = PropertyMock(
        side_effect=[HTTPStatus.BAD_REQUEST, sentinel],
    )
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_response_truthiness_hook() -> None:
    sentinel = CredentialsValidateFailedError("response truthiness failed")
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.side_effect = RuntimeError("json failed")
    response.__bool__.side_effect = sentinel
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_status_failure_truthiness_hook() -> None:
    sentinel = CredentialsValidateFailedError("response truthiness failed")
    response = MagicMock(text="failed")
    type(response).status_code = PropertyMock(
        side_effect=[HTTPStatus.BAD_REQUEST, RuntimeError("status failed")],
    )
    response.__bool__.side_effect = sentinel
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_truth_tests_stream_mode_once() -> None:
    stream_result = StatefulTruth()
    stream_mode = MagicMock()
    stream_mode.__eq__.return_value = stream_result
    response = MagicMock(status_code=HTTPStatus.OK)
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": stream_mode,
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ) as post:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert stream_result.calls == 1
    assert post.call_args.kwargs["stream"] is True
    response.json.assert_not_called()
