import pytest
from pydantic import JsonValue, ValidationError

from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    AudioPromptMessageContent,
    DeveloperPromptMessage,
    DocumentPromptMessageContent,
    ImagePromptMessageContent,
    MultiModalPromptMessageContent,
    PromptMessage,
    PromptMessageRole,
    SystemPromptMessage,
    TextPromptMessageContent,
    ToolPromptMessage,
    UserPromptMessage,
    VideoPromptMessageContent,
    ensure_prompt_message,
)


def test_build_prompt_message_with_prompt_message_contents() -> None:
    prompt = UserPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")])
    assert isinstance(prompt.content, list)
    assert isinstance(prompt.content[0], TextPromptMessageContent)
    assert prompt.content[0].data == "Hello, World!"


def test_dump_prompt_message() -> None:
    example_url = "https://example.com/image.jpg"
    prompt = UserPromptMessage(
        content=[
            TextPromptMessageContent(
                data="Hello, World!",
            ),
            ImagePromptMessageContent(
                url=example_url,
                format="jpeg",
                mime_type="image/jpeg",
            ),
        ]
    )
    data = prompt.model_dump()
    assert data["content"][0].get("data") == "Hello, World!"
    assert data["content"][1].get("url") == example_url


def test_validate_prompt_message() -> None:
    json_data = {
        "content": [
            {"type": "text", "data": "Hello, World!"},
            {
                "type": "image",
                "url": "https://example.com/image.jpg",
                "format": "jpeg",
                "mime_type": "image/jpeg",
            },
        ]
    }
    prompt = UserPromptMessage.model_validate(json_data)
    assert isinstance(prompt, UserPromptMessage)
    prompt_content = prompt.content
    assert isinstance(prompt_content, list)
    assert isinstance(prompt_content[0], TextPromptMessageContent)
    assert prompt_content[0].data == "Hello, World!"
    assert isinstance(prompt_content[1], ImagePromptMessageContent)
    assert prompt_content[1].url == "https://example.com/image.jpg"


def test_ensure_prompt_message_uses_role_specific_class() -> None:
    message = ensure_prompt_message({"role": "assistant", "content": "ok"})
    assert isinstance(message, AssistantPromptMessage)

    prompt = UserPromptMessage(content="hello")
    assert ensure_prompt_message(prompt) is prompt

    enum_message = ensure_prompt_message(
        {"role": PromptMessageRole.USER, "content": "hello"},
    )
    assert isinstance(enum_message, UserPromptMessage)


def test_ensure_prompt_message_rejects_non_mapping() -> None:
    with pytest.raises(TypeError, match="PromptMessage or a Mapping"):
        ensure_prompt_message("assistant")


@pytest.mark.parametrize(
    ("role", "message_type"),
    [
        ("system", SystemPromptMessage),
        ("developer", DeveloperPromptMessage),
        ("user", UserPromptMessage),
        ("assistant", AssistantPromptMessage),
        ("tool", ToolPromptMessage),
    ],
)
def test_prompt_roles_survive_wire_roundtrip(
    role: str, message_type: type[PromptMessage]
) -> None:
    payload = {"role": role, "content": "message", "name": "sender"}
    if role == "tool":
        payload["tool_call_id"] = "call-1"

    message = ensure_prompt_message(payload)

    assert type(message) is message_type
    assert message.model_dump(mode="json", include=set(payload)) == payload
    assert ensure_prompt_message(message.model_dump(mode="json")) == message


@pytest.mark.parametrize(
    ("media_type", "content_type"),
    [
        ("image", ImagePromptMessageContent),
        ("audio", AudioPromptMessageContent),
        ("video", VideoPromptMessageContent),
        ("document", DocumentPromptMessageContent),
    ],
)
def test_multimodal_messages_preserve_media_and_extract_only_text(
    media_type: str, content_type: type[MultiModalPromptMessageContent]
) -> None:
    payload = {
        "type": media_type,
        "format": "binary",
        "mime_type": "application/octet-stream",
        "base64_data": "AP8=",
        "filename": "asset.bin",
        "opaque_body": {"provider_id": "media-1"},
    }
    message = UserPromptMessage(
        content=(
            {"type": "text", "data": "before "},
            payload,
            TextPromptMessageContent(data="after"),
        )
    )

    assert isinstance(message.content, list)
    media = message.content[1]
    assert isinstance(media, content_type)
    assert media.data == "data:application/octet-stream;base64,AP8="
    assert media.filename == "asset.bin"
    assert media.opaque_body == {"provider_id": "media-1"}
    assert message.get_text_content() == "before after"
    assert UserPromptMessage.model_validate_json(message.model_dump_json()) == message
    media.url = "https://example.com/asset.bin"
    assert media.data == "https://example.com/asset.bin"


@pytest.mark.parametrize("content", [None, "", "hello", []])
def test_plain_prompt_content_presence(content: str | list | None) -> None:
    message = UserPromptMessage(content=content)

    assert message.is_empty() is (not content)
    assert message.get_text_content() == (content or "")


@pytest.mark.parametrize("has_content", [False, True])
@pytest.mark.parametrize("has_tool_call", [False, True])
def test_assistant_message_with_tool_call_is_not_empty(
    has_content: bool, has_tool_call: bool
) -> None:
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "weather", "arguments": "{}"},
    }
    message = AssistantPromptMessage(
        content="hello" if has_content else None,
        tool_calls=[tool_call] if has_tool_call else [],
    )

    assert message.is_empty() is (not has_content and not has_tool_call)


@pytest.mark.parametrize("snapshot", [None, {}, [], "", 0, False, {"signature": "s"}])
def test_assistant_replay_state_counts_as_content(snapshot: JsonValue) -> None:
    message = AssistantPromptMessage(opaque_body=snapshot)

    assert message.is_empty() is (snapshot is None)


@pytest.mark.parametrize("has_content", [False, True])
@pytest.mark.parametrize("has_call_id", [False, True])
def test_tool_message_with_call_id_is_not_empty(
    has_content: bool, has_call_id: bool
) -> None:
    message = ToolPromptMessage(
        content="result" if has_content else None,
        tool_call_id="call-1" if has_call_id else "",
    )

    assert message.is_empty() is (not has_content and not has_call_id)


@pytest.mark.parametrize(
    ("call_id", "expected"), [(None, ""), (123, "123"), ("call-1", "call-1")]
)
def test_partial_tool_calls_normalize_missing_strings(
    call_id: str | int | None, expected: str
) -> None:
    message = ensure_prompt_message({
        "role": "assistant",
        "tool_calls": [
            {
                "id": call_id,
                "type": None,
                "function": {"name": None, "arguments": None},
            }
        ],
    })

    assert isinstance(message, AssistantPromptMessage)
    assert message.tool_calls[0].model_dump() == {
        "id": expected,
        "type": "",
        "function": {"name": "", "arguments": ""},
    }


@pytest.mark.parametrize("content", [[{"type": "unknown"}], [{"type": "text"}]])
def test_invalid_content_is_rejected_before_provider_use(content: list[dict]) -> None:
    with pytest.raises(ValidationError):
        UserPromptMessage(content=content)


def test_non_mapping_content_is_rejected() -> None:
    with pytest.raises(TypeError, match="invalid prompt message content"):
        UserPromptMessage(content=[42])
