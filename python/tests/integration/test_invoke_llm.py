import json
import threading
from flask import Response
from yarl import URL
from dify_plugin.config.integration_config import IntegrationConfig
from dify_plugin.core.entities.plugin.request import ModelActions, ModelInvokeLLMRequest, PluginInvokeType
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.integration.run import PluginRunner
import requests

_MARKETPLACE_API_URL = "https://marketplace.dify.ai"


def openai_server_mock():
    from flask import Flask, request, jsonify
    import flask.cli

    flask.cli.show_server_banner = lambda *args: None

    app = Flask(__name__)

    @app.route("/v1/chat/completions", methods=["POST"])
    def chat_completions():
        request_body = request.get_json(force=True)
        if request_body.get("stream"):

            def stream_response():
                yield "data: "
                yield json.dumps({"choices": [{"message": {"content": "Hello, world!"}}]})
                yield "\n\n"

            return Response(stream_response(), mimetype="text/event-stream")
        else:
            return jsonify(
                {
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": 1715806438,
                    "model": request_body["model"],
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "Hello, world!"},
                            "index": 0,
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                }
            )

    app.run(port=11451)


def test_invoke_llm():
    # download latest langgenius-openai plugin
    url = str(URL(_MARKETPLACE_API_URL) / "api/v1/plugins/batch")
    response = requests.post(url, json={"plugin_ids": ["langgenius/openai"]})
    latest_identifier = response.json()["data"]["plugins"][0]["latest_package_identifier"]

    url = str((URL(_MARKETPLACE_API_URL) / "api/v1/plugins/download").with_query(unique_identifier=latest_identifier))
    response = requests.get(url)

    # save the response to a file
    with open("langgenius-openai.difypkg", "wb") as f:
        f.write(response.content)

    # start mocked openai server
    openai_server = threading.Thread(target=openai_server_mock, daemon=True)
    openai_server.start()

    try:
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
                        "openai_api_base": "http://localhost:11451",
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
    finally:
        # Ensure the test doesn't hang even if there's an exception
        if openai_server.is_alive():
            # The thread will automatically terminate when the main thread exits
            # because it's a daemon thread
            pass
