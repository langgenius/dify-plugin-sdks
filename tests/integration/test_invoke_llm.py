import pathlib

import pytest

from dify_plugin.config.integration_config import IntegrationConfig, find_dify_cli_path
from dify_plugin.core.entities.plugin.request import (
    ModelActions,
    ModelInvokeLLMRequest,
    PluginInvokeType,
)
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.integration.run import PluginRunner

# Import requests only after dify_plugin applies its gevent patch.
# isort: split

import requests

_OPENAI_PLUGIN_URL = (
    "https://marketplace.dify.ai/api/v1/plugins/langgenius/openai/1.0.0/download"
)

pytestmark = pytest.mark.skipif(
    find_dify_cli_path() is None,
    reason="dify cli not found; install dify-plugin-cli to run integration tests",
)


def test_invoke_llm(openai_mock_server: str) -> None:
    response = requests.get(_OPENAI_PLUGIN_URL, timeout=10)
    response.raise_for_status()

    # save the response to a file
    pathlib.Path("langgenius-openai.difypkg").write_bytes(response.content)

    # run the plugin
    with PluginRunner(
        config=IntegrationConfig(), plugin_package_path="langgenius-openai.difypkg"
    ) as runner:
        for result in runner.invoke(
            access_type=PluginInvokeType.Model,
            access_action=ModelActions.InvokeLLM,
            payload=ModelInvokeLLMRequest(
                prompt_messages=[
                    UserPromptMessage(content="Hello, world!"),
                ],
                user_id="",
                provider="openai",
                model_type=ModelType.LLM,
                model="gpt-5.6",
                credentials={
                    "api_protocol": "chat",
                    "openai_api_base": openai_mock_server,
                    "openai_api_key": "test",
                },
                model_parameters={},
                stop=[],
                tools=[],
                stream=False,
            ),
            response_type=LLMResultChunk,
        ):
            assert result.delta.message.content == "Hello, world!"
