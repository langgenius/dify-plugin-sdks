from yarl import URL

from dify_plugin.config.integration_config import IntegrationConfig
from dify_plugin.core.entities.plugin.request import ModelActions, ModelInvokeLLMRequest, PluginInvokeType
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.integration.run import PluginRunner
from tests.consts.mockserver import OPENAI_MOCK_SERVER_PORT

_MARKETPLACE_API_URL = "https://marketplace.dify.ai"


def test_invoke_llm():
    import requests

    # download latest langgenius-openai plugin
    url = str(URL(_MARKETPLACE_API_URL) / "api/v1/plugins/batch")
    response = requests.post(url, json={"plugin_ids": ["langgenius/openai"]}, timeout=10)
    latest_identifier = response.json()["data"]["plugins"][0]["latest_package_identifier"]

    url = str((URL(_MARKETPLACE_API_URL) / "api/v1/plugins/download").with_query(unique_identifier=latest_identifier))
    response = requests.get(url, timeout=10)

    # save the response to a file
    with open("langgenius-openai.difypkg", "wb") as f:
        f.write(response.content)

    # run the plugin
    with PluginRunner(config=IntegrationConfig(), plugin_package_path="langgenius-openai.difypkg") as runner:
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
                model="gpt-3.5-turbo",
                credentials={
                    "openai_api_base": f"http://localhost:{OPENAI_MOCK_SERVER_PORT}",
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
