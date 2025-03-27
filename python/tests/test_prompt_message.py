from dify_plugin.entities.model.message import ImagePromptMessageContent, TextPromptMessageContent, UserPromptMessage


def test_build_prompt_message_with_prompt_message_contents():
    prompt = UserPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")])
    assert isinstance(prompt.content, list)
    assert isinstance(prompt.content[0], TextPromptMessageContent)
    assert prompt.content[0].data == "Hello, World!"


def test_dump_prompt_message():
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


def test_validate_prompt_message():
    json_data = {
        "content": [
            {"type": "text", "data": "Hello, World!"},
            {"type": "image", "url": "https://example.com/image.jpg", "format": "jpeg", "mime_type": "image/jpeg"},
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
