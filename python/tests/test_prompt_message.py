from dify_plugin.entities.model.message import TextPromptMessageContent, UserPromptMessage


def test_build_prompt_message_with_prompt_message_contents():
    prompt = UserPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")])
    assert isinstance(prompt.content, list)
    assert isinstance(prompt.content[0], TextPromptMessageContent)
    assert prompt.content[0].data == "Hello, World!"
