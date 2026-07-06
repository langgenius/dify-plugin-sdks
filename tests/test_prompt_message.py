from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessageRole,
    TextPromptMessageContent,
    UserPromptMessage,
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
