import json

import flask.cli
from flask import Flask, Response, jsonify, request

from tests.consts.mockserver import OPENAI_MOCK_SERVER_PORT

flask.cli.show_server_banner = lambda *args: None


def openai_server_mock():
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

    app.run(port=OPENAI_MOCK_SERVER_PORT)
