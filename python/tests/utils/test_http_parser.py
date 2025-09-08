import json

from flask import Flask, jsonify, make_response
from flask import request as flask_request

from dify_plugin.core.utils.http_parser import (
    deserialize_request,
    deserialize_response,
    serialize_request,
    serialize_response,
)


def test_http_request_roundtrip():
    """Test all HTTP request attributes are preserved through serialization"""
    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook():
        original = flask_request
        raw = serialize_request(original)
        reconstructed = deserialize_request(raw)

        assert reconstructed.method == original.method
        assert reconstructed.path == original.path
        assert reconstructed.query_string == original.query_string
        assert reconstructed.get_json() == original.get_json()
        assert reconstructed.get_data() == original.get_data()

        for key in ["Authorization", "X-Webhook-Signature", "User-Agent"]:
            if key in original.headers:
                assert reconstructed.headers.get(key) == original.headers.get(key)

        for key in original.cookies:
            assert reconstructed.cookies.get(key) == original.cookies.get(key)

        return jsonify({"status": "ok"})

    with app.test_client() as client:
        client.set_cookie("session_id", "abc123")
        client.set_cookie("user", "john")

        response = client.post(
            "/webhook?param=value&array[]=1&array[]=2",
            json={"event": "test.event", "data": {"id": 123, "items": [1, 2, 3]}},
            headers={
                "Authorization": "Bearer token",
                "X-Webhook-Signature": "sha256=signature",
                "User-Agent": "TestClient/1.0",
            },
        )

        assert response.status_code == 200


def test_http_response_roundtrip():
    """Test all HTTP response attributes are preserved through serialization"""
    app = Flask(__name__)

    @app.route("/api/<path:path>")
    def api(path):
        if path == "error":
            response = make_response(jsonify({"error": "Not found"}), 404)
            response.headers["X-Error"] = "NOTFOUND"
        else:
            response = make_response(jsonify({"data": {"id": 1, "name": "test"}}), 200)
            response.headers["X-Version"] = "v1"
            response.headers["Cache-Control"] = "max-age=3600"

        response.set_cookie("token", "new-token")
        return response

    with app.test_client() as client:
        response = client.get("/api/data")
        raw = serialize_response(response)
        reconstructed = deserialize_response(raw)

        assert reconstructed.status_code == 200
        assert "X-Version" in reconstructed.headers
        assert json.loads(reconstructed.get_data())["data"]["id"] == 1

        error_response = client.get("/api/error")
        raw_error = serialize_response(error_response)
        reconstructed_error = deserialize_response(raw_error)

        assert reconstructed_error.status_code == 404
        assert "X-Error" in reconstructed_error.headers


def test_form_and_binary_data():
    """Test form data and binary content preservation"""
    app = Flask(__name__)

    @app.route("/upload", methods=["POST"])
    def upload():
        raw = serialize_request(flask_request)
        reconstructed = deserialize_request(raw)

        if flask_request.content_type == "application/x-www-form-urlencoded":
            assert reconstructed.form.to_dict() == flask_request.form.to_dict()
        else:
            assert reconstructed.get_data() == flask_request.get_data()

        binary_response = bytes(range(256))
        response = make_response(binary_response)
        response.headers["Content-Type"] = "application/octet-stream"
        return response

    with app.test_client() as client:
        response = client.post("/upload", data={"field1": "value1", "field2": "value2"})
        assert response.status_code == 200

        binary_data = b"\x00\x01\x02\xff\xfe\xfd" * 100
        response = client.post("/upload", data=binary_data, headers={"Content-Type": "application/octet-stream"})

        raw_response = serialize_response(response)
        reconstructed = deserialize_response(raw_response)
        assert len(reconstructed.get_data()) == 256


def test_special_cases():
    """Test edge cases and special characters"""
    app = Flask(__name__)

    @app.route("/test", methods=["GET", "POST"])
    def test():
        if flask_request.method == "GET":
            return "", 204

        raw = serialize_request(flask_request)
        reconstructed = deserialize_request(raw)
        json_data = reconstructed.get_json()
        assert json_data == flask_request.get_json()
        return jsonify(json_data)

    with app.test_client() as client:
        response = client.get("/test")
        assert response.status_code == 204

        raw = serialize_response(response)
        reconstructed = deserialize_response(raw)
        assert reconstructed.status_code == 204
        assert reconstructed.get_data() == b""

        response = client.post(
            "/test", json={"japanese": "こんにちは", "emoji": "😀🎉", "special": "café", "symbols": "α β γ"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["emoji"] == "😀🎉"
