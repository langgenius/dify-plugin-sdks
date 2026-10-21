from collections.abc import Generator
from copy import deepcopy
from types import MappingProxyType
from unittest.mock import Mock

import pytest

from dify_plugin.entities.model import AIModelEntity, ModelType, ParameterRule
from dify_plugin.entities.model.llm import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessage,
    SystemPromptMessage,
    TextPromptMessageContent,
    UserPromptMessage,
)
from dify_plugin.errors.model import InvokeConnectionError, InvokeError
from tests.interfaces.model.utils import StubLLM


@pytest.fixture
def llm() -> StubLLM:
    return StubLLM([
        AIModelEntity(
            model="model",
            model_type=ModelType.LLM,
            model_properties={},
            parameter_rules=[
                ParameterRule.model_validate({
                    "name": "response_format",
                    "type": "string",
                    "options": ["JSON", "XML"],
                })
            ],
        )
    ])


def _chunk(content: str) -> LLMResultChunk:
    return LLMResultChunk(
        model="model",
        delta=LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(content=content),
        ),
    )


@pytest.mark.parametrize("response_format", ["JSON", "XML"])
@pytest.mark.parametrize("split_at", [1, 2, 3, 6, 12])
def test_structured_stream_strips_fragmented_fences_and_preserves_usage(
    llm: StubLLM,
    response_format: str,
    split_at: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = '{"answer":"ok"}' if response_format == "JSON" else "<answer>ok</answer>"
    text = f"```{response_format.lower()}\n{body}\n```ignored"
    usage = LLMUsage.empty_usage()
    usage.prompt_tokens = 7
    usage.completion_tokens = 3
    usage.total_tokens = 10
    terminal = _chunk("")
    terminal.delta.usage = usage
    terminal.delta.finish_reason = "stop"
    terminal.system_fingerprint = "provider-fingerprint"
    expected_terminal = terminal.model_copy(deep=True)

    def response() -> Generator[LLMResultChunk]:
        yield _chunk(text[:split_at])
        yield _chunk(text[split_at:])
        yield terminal

    monkeypatch.setattr(llm, "_invoke", Mock(return_value=response()))
    chunks = list(
        llm.invoke(
            "model",
            {},
            [],
            model_parameters={"response_format": response_format},
        )
    )

    assert (
        "".join(str(chunk.delta.message.content or "") for chunk in chunks)
        == body + "\n"
    )
    assert chunks[-1] == expected_terminal
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].system_fingerprint == "provider-fingerprint"
    assert llm.started_at == 0


@pytest.mark.parametrize("leading_empty", [False, True])
def test_structured_stream_accepts_plain_json_and_empty_role_chunks(
    llm: StubLLM,
    leading_empty: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def response() -> Generator[LLMResultChunk]:
        if leading_empty:
            yield _chunk("")
        yield _chunk('{"answer":')
        yield _chunk('"ok"}')

    monkeypatch.setattr(llm, "_invoke", Mock(return_value=response()))
    chunks = list(
        llm.invoke(
            "model",
            {},
            [],
            model_parameters={"response_format": "JSON"},
        )
    )

    assert (
        "".join(str(chunk.delta.message.content or "") for chunk in chunks)
        == '{"answer":"ok"}'
    )
    assert llm.started_at == 0


@pytest.mark.parametrize("text_parts", [False, True])
def test_structured_output_prepares_system_and_user_instructions(
    llm: StubLLM,
    text_parts: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_content = (
        [TextPromptMessageContent(data="question")] if text_parts else "question"
    )
    prompts = [
        SystemPromptMessage(content="Return the answer"),
        UserPromptMessage(content=user_content),
    ]
    provider = Mock(return_value=(_chunk("{}") for _ in range(1)))
    monkeypatch.setattr(llm, "_invoke", provider)

    chunks = list(
        llm.invoke(
            "model",
            {},
            prompts,
            model_parameters={"response_format": "JSON"},
            stop=["END"],
            user="user-1",
        )
    )

    assert "".join(str(chunk.delta.message.content or "") for chunk in chunks) == "{}"
    forwarded = provider.call_args.kwargs
    assert forwarded["model_parameters"] == {}
    assert forwarded["stop"] == ["END", "\n```", "```\n"]
    assert forwarded["user"] == "user-1"
    assert "Return the answer" in forwarded["prompt_messages"][0].content
    content = forwarded["prompt_messages"][-1].content
    text = content[-1].data if text_parts else content
    assert text == "question\n```JSON\n"


def test_empty_structured_stream_keeps_provider_error(
    llm: StubLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "_invoke", Mock(return_value=(_chunk("") for _ in ())))

    with pytest.raises(InvokeError) as exc_info:
        list(
            llm.invoke(
                "model",
                {},
                [],
                model_parameters={"response_format": "JSON"},
            )
        )
    assert isinstance(exc_info.value.__cause__, StopIteration)
    assert llm.started_at == 0


@pytest.mark.parametrize("first_content", ["```json\n{}", "{}"])
@pytest.mark.parametrize("consume_first_chunk", [False, True])
def test_closing_structured_stream_closes_provider(
    llm: StubLLM,
    first_content: str,
    consume_first_chunk: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = []

    def response() -> Generator[LLMResultChunk]:
        try:
            yield _chunk(first_content)
            pytest.fail("Closing the public stream must not consume more provider data")
        finally:
            closed.append(True)

    provider_stream = response()
    monkeypatch.setattr(llm, "_invoke", Mock(return_value=provider_stream))
    invoke = llm.invoke if consume_first_chunk else llm._code_block_mode_wrapper
    stream = invoke("model", {}, [], model_parameters={"response_format": "JSON"})
    assert isinstance(stream, Generator)
    if consume_first_chunk:
        next(stream)
    stream.close()

    assert closed == [True]
    assert llm.started_at == 0


def test_structured_stream_maps_provider_failure_and_closes(
    llm: StubLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = TimeoutError("provider stalled")
    closed = []

    def response() -> Generator[LLMResultChunk]:
        try:
            yield _chunk("```json\n{}")
            raise error
        finally:
            closed.append(True)

    monkeypatch.setattr(llm, "_invoke", Mock(return_value=response()))

    with pytest.raises(InvokeConnectionError) as exc_info:
        list(llm.invoke("model", {}, [], model_parameters={"response_format": "JSON"}))

    assert exc_info.value.__cause__ is error
    assert closed == [True]
    assert llm.started_at == 0


@pytest.mark.parametrize("fenced", [False, True])
@pytest.mark.parametrize("leading_empty", [False, True])
def test_structured_stream_preserves_backticks_inside_json_strings(
    llm: StubLLM, fenced: bool, leading_empty: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = '{"text":"one`two``three"}'
    source = f"```json\n{body}\n```" if fenced else body

    def response() -> Generator[LLMResultChunk]:
        if leading_empty:
            yield _chunk("")
        for character in source:
            yield _chunk(character)

    monkeypatch.setattr(llm, "_invoke", Mock(return_value=response()))

    chunks = list(
        llm.invoke("model", {}, [], model_parameters={"response_format": "JSON"})
    )

    expected = body + "\n" if fenced else body
    assert (
        "".join(str(chunk.delta.message.content or "") for chunk in chunks) == expected
    )
    assert llm.started_at == 0


def test_structured_output_preserves_image_content_and_complete_provider_result(
    llm: StubLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = ImagePromptMessageContent(
        format="png", mime_type="image/png", url="https://example.com/image.png"
    )
    response = LLMResult(
        model="model",
        message=AssistantPromptMessage(content='{"answer":42}'),
        usage=LLMUsage.empty_usage(),
    )
    response.usage.prompt_tokens = 11
    response.usage.completion_tokens = 2
    response.usage.total_tokens = 13
    expected_response = response.model_copy(deep=True)
    provider = Mock(return_value=response)
    monkeypatch.setattr(llm, "_invoke", provider)

    chunks = list(
        llm.invoke(
            "model",
            {},
            [UserPromptMessage(content=[media])],
            model_parameters={"response_format": "JSON"},
            stream=False,
        )
    )

    assert len(chunks) == 1
    assert chunks[0].delta.message == expected_response.message
    assert chunks[0].delta.usage == expected_response.usage
    forwarded = provider.call_args.kwargs
    assert forwarded["stream"] is False
    assert forwarded["prompt_messages"][-1].content == [media]
    assert "valid JSON object" in forwarded["prompt_messages"][0].content


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('```json\n{"answer":42}\n```\nexplanation', '{"answer":42}\nexplanation'),
        ('{"text":"use ``` to mark code"}', '{"text":"use to mark code"}'),
        (
            '```json\n{"text":"use ``` to mark code"}\n```\nexplanation',
            '{"text":"use to mark code"}\nexplanation',
        ),
    ],
    ids=["empty-before-fence", "inline-backticks", "fenced-inline-backticks"],
)
@pytest.mark.parametrize("chunk_size", [1, 2, 7, 100])
def test_structured_stream_keeps_fence_handling_after_empty_first_chunk(
    llm: StubLLM,
    source: str,
    expected: str,
    chunk_size: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leading = _chunk("")
    terminal = _chunk("")
    terminal.delta.usage = LLMUsage.empty_usage()
    terminal.delta.finish_reason = "stop"
    terminal.system_fingerprint = "provider-revision"
    expected_leading = leading.model_copy(deep=True)
    expected_terminal = terminal.model_copy(deep=True)

    def response() -> Generator[LLMResultChunk]:
        yield leading
        for offset in range(0, len(source), chunk_size):
            text = source[offset : offset + chunk_size]
            yield _chunk(text)
        yield terminal

    monkeypatch.setattr(llm, "_invoke", Mock(return_value=response()))

    chunks = list(
        llm.invoke("model", {}, [], model_parameters={"response_format": "JSON"})
    )

    assert (
        "".join(chunk.delta.message.get_text_content() for chunk in chunks) == expected
    )
    assert chunks[0] == expected_leading
    assert chunks[-1] == expected_terminal
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].system_fingerprint == "provider-revision"
    assert llm.started_at == 0


@pytest.mark.parametrize("text_parts", [False, True])
def test_structured_invocations_keep_input_updates_when_reused(
    llm: StubLLM, text_parts: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = [
        SystemPromptMessage(content="Return the answer"),
        UserPromptMessage(
            content=[TextPromptMessageContent(data="question")]
            if text_parts
            else "question"
        ),
    ]
    stop = ["END"]
    calls = []

    def invoke(**kwargs: object) -> LLMResult:
        calls.append(deepcopy(kwargs))
        return LLMResult(
            model="model",
            message=AssistantPromptMessage(content="{}"),
            usage=LLMUsage.empty_usage(),
        )

    monkeypatch.setattr(llm, "_invoke", invoke)
    for _ in range(2):
        list(llm.invoke("model", {}, prompts, {"response_format": "JSON"}, stop=stop))

    instruction_prefix = (
        "You should always follow the instructions and output a valid JSON object.\n"
        "The structure of the JSON object you can found in the instructions, "
        'use {"answer": "$your_answer"} as the default structure\n'
        "if you are not sure about the structure.\n\n<instructions>\n"
    )
    first_system = instruction_prefix + "Return the answer\n</instructions>\n"
    assert calls[0]["prompt_messages"][0].content == first_system
    assert calls[1]["prompt_messages"][0].content == (
        instruction_prefix + first_system + "\n</instructions>\n"
    )
    assert calls[0]["prompt_messages"][-1].get_text_content() == "question\n```JSON\n"
    assert (
        calls[1]["prompt_messages"][-1].get_text_content()
        == "question\n```JSON\n\n```JSON\n"
    )
    assert calls[0]["stop"] == ["END", "\n```", "```\n"]
    assert calls[1]["stop"] == ["END", "\n```", "```\n", "\n```", "```\n"]
    assert prompts == calls[1]["prompt_messages"]
    assert stop == calls[1]["stop"]


def test_structured_wrapper_keeps_response_format_pop_when_parameters_are_reused(
    llm: StubLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = [UserPromptMessage(content="question")]
    parameters = {"response_format": "JSON"}
    stop = ["END"]
    calls = []

    def invoke(**kwargs: object) -> LLMResult:
        calls.append(deepcopy(kwargs))
        return LLMResult(
            model="model",
            message=AssistantPromptMessage(content="{}"),
            usage=LLMUsage.empty_usage(),
        )

    monkeypatch.setattr(llm, "_invoke", invoke)
    for _ in range(2):
        llm._code_block_mode_wrapper(
            "model", {}, prompts, parameters, stop=stop, stream=False
        )

    assert parameters == {}
    assert calls[0] == calls[1]
    assert calls[0]["model_parameters"] == {}
    assert prompts[-1].content == "question\n```JSON\n"
    assert stop == ["END", "\n```", "```\n"]


@pytest.mark.parametrize("text_parts", [False, True])
def test_structured_invocations_preserve_repeated_prompt_references(
    llm: StubLLM, text_parts: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = TextPromptMessageContent(data="question")
    prompt = UserPromptMessage(content=[text] if text_parts else "question")
    prompts = [prompt, prompt]
    provider = Mock(
        return_value=LLMResult(
            model="model",
            message=AssistantPromptMessage(content="{}"),
            usage=LLMUsage.empty_usage(),
        )
    )
    monkeypatch.setattr(llm, "_invoke", provider)

    for expected in ["question\n```JSON\n", "question\n```JSON\n\n```JSON\n"]:
        list(
            llm.invoke("model", {}, prompts, {"response_format": "JSON"}, stream=False)
        )
        forwarded = provider.call_args.kwargs["prompt_messages"]
        assert [message.get_text_content() for message in forwarded[1:]] == [
            expected,
            expected,
        ]
        assert forwarded[1] is forwarded[2] is prompt
        assert prompts is forwarded
        assert prompt.get_text_content() == expected
        assert text.data == (expected if text_parts else "question")


@pytest.mark.parametrize("shared_content_list", [False, True])
def test_structured_invocations_preserve_shared_text_references(
    llm: StubLLM, shared_content_list: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = TextPromptMessageContent(data="question")
    independent = TextPromptMessageContent(data="question")
    previous = AssistantPromptMessage(content=[shared])
    prompt = UserPromptMessage(content=[independent, shared, shared])
    if shared_content_list:
        previous.content = prompt.content
    prompts = [previous, prompt]
    provider = Mock(
        return_value=LLMResult(
            model="model",
            message=AssistantPromptMessage(content="{}"),
            usage=LLMUsage.empty_usage(),
        )
    )
    monkeypatch.setattr(llm, "_invoke", provider)

    for expected in ["question\n```JSON\n", "question\n```JSON\n\n```JSON\n"]:
        list(
            llm.invoke("model", {}, prompts, {"response_format": "JSON"}, stream=False)
        )
        forwarded = provider.call_args.kwargs["prompt_messages"]
        first, last = forwarded[1:]
        assert [part.data for part in last.content] == ["question", expected, expected]
        assert first.content[-1] is last.content[-1]
        assert last.content[1] is last.content[2]
        assert (first.content is last.content) is shared_content_list
        assert last.content[0] is independent
        assert shared.data == expected
        assert independent.data == "question"
        assert previous.content[-1] is prompt.content[-1] is shared


@pytest.mark.parametrize("text_parts", [False, True])
def test_structured_invocation_preserves_provider_prompt_subclasses(
    llm: StubLLM, text_parts: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ProviderPrompt(UserPromptMessage):
        provider_state: object

    class ProviderText(TextPromptMessageContent):
        provider_state: object

    state = MappingProxyType({"tenant": "test"})
    text = ProviderText(data="question", provider_state=state)
    prompt = ProviderPrompt(
        content=[text] if text_parts else "question", provider_state=state
    )
    provider = Mock(
        return_value=LLMResult(
            model="model",
            message=AssistantPromptMessage(content="{}"),
            usage=LLMUsage.empty_usage(),
        )
    )
    monkeypatch.setattr(llm, "_invoke", provider)

    chunks = list(
        llm.invoke("model", {}, [prompt], {"response_format": "JSON"}, stream=False)
    )

    assert chunks[0].delta.message.content == "{}"
    forwarded = provider.call_args.kwargs["prompt_messages"][-1]
    assert forwarded is prompt
    assert isinstance(forwarded, ProviderPrompt)
    assert forwarded.provider_state is state
    if text_parts:
        assert isinstance(forwarded.content[0], ProviderText)
        assert forwarded.content[0].provider_state is state
        assert forwarded.content[0].data == "question\n```JSON\n"
        assert prompt.content == [text]
        assert text.data == "question\n```JSON\n"
    else:
        assert forwarded.content == "question\n```JSON\n"
        assert prompt.content == "question\n```JSON\n"


@pytest.mark.parametrize(
    ("source", "expected", "response_format", "finish_reason"),
    [
        ("\n \t```json\n{}\n```", "\n \t{}\n", "JSON", "stop"),
        ("<answer><![CDATA[\n`", "<answer><![CDATA[\n", "XML", "length"),
        ("<answer><![CDATA[\n``", "<answer><![CDATA[\n", "XML", "length"),
    ],
)
def test_structured_stream_keeps_whitespace_and_unfinished_fence_handling(
    llm: StubLLM,
    source: str,
    expected: str,
    response_format: str,
    finish_reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal = _chunk("")
    terminal.delta.finish_reason = finish_reason
    terminal.delta.usage = LLMUsage.empty_usage()

    def response() -> Generator[LLMResultChunk]:
        for character in source:
            yield _chunk(character)
        yield terminal

    monkeypatch.setattr(llm, "_invoke", Mock(return_value=response()))
    chunks = list(llm.invoke("model", {}, [], {"response_format": response_format}))

    assert (
        "".join(chunk.delta.message.get_text_content() for chunk in chunks) == expected
    )
    assert [chunk.delta.finish_reason for chunk in chunks if chunk.delta.usage] == [
        finish_reason
    ]
    assert llm.started_at == 0


@pytest.mark.parametrize("fenced", [False, True])
@pytest.mark.parametrize("chunk_size", [1, 7])
@pytest.mark.parametrize(
    ("body", "plain_output", "fenced_output"),
    [
        (
            "<answer><![CDATA[\n```example\n]]></answer>",
            "<answer><![CDATA[\n]]></answer>",
            "<answer><![CDATA[\n",
        ),
        (
            '<answer attr="\n```example\n">ok</answer>',
            '<answer attr="\n">ok</answer>',
            '<answer attr="\n',
        ),
        (
            "<answer><!--\n```example\n--></answer>",
            "<answer><!--\n--></answer>",
            "<answer><!--\n",
        ),
        (
            '<?xml version="1.0"?><answer>中文</answer>',
            '<?xml version="1.0"?><answer>中文</answer>',
            '<?xml version="1.0"?><answer>中文</answer>\n',
        ),
        (" \n<answer/>", " \n<answer/>", " \n<answer/>\n"),
    ],
)
def test_structured_xml_keeps_existing_fence_handling_and_stops(
    llm: StubLLM,
    fenced: bool,
    chunk_size: int,
    body: str,
    plain_output: str,
    fenced_output: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = f"```xml\n{body}\n```" if fenced else body
    terminal = _chunk("")
    terminal.delta.finish_reason = "stop"
    terminal.delta.usage = LLMUsage.empty_usage()
    expected_terminal = terminal.model_copy(deep=True)

    def response() -> Generator[LLMResultChunk]:
        for offset in range(0, len(source), chunk_size):
            yield _chunk(source[offset : offset + chunk_size])
        yield terminal

    provider = Mock(return_value=response())
    monkeypatch.setattr(llm, "_invoke", provider)

    chunks = list(llm.invoke("model", {}, [], {"response_format": "XML"}, stop=["END"]))

    assert "".join(chunk.delta.message.get_text_content() for chunk in chunks) == (
        fenced_output if fenced else plain_output
    )
    assert chunks[-1] == expected_terminal
    assert provider.call_args.kwargs["stop"] == ["END", "\n```", "```\n"]


@pytest.mark.parametrize(
    ("first_content", "expected_hook"),
    [
        ("```json\n{}", "_code_block_mode_stream_processor_with_backtick"),
        ("{}", "_code_block_mode_stream_processor"),
        ("", "_code_block_mode_stream_processor"),
    ],
)
def test_structured_stream_calls_existing_provider_processor_override(
    llm: StubLLM,
    first_content: str,
    expected_hook: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, last, result = _chunk(first_content), _chunk("tail"), _chunk("custom output")
    received = []

    def processor(
        model: str,
        prompt_messages: list[PromptMessage],
        input_generator: Generator[LLMResultChunk],
    ) -> Generator[LLMResultChunk]:
        received.append((model, prompt_messages, list(input_generator)))
        yield result

    normal = Mock(side_effect=processor)
    fenced = Mock(side_effect=processor)
    monkeypatch.setattr(llm, "_code_block_mode_stream_processor", normal)
    monkeypatch.setattr(llm, "_code_block_mode_stream_processor_with_backtick", fenced)
    provider = Mock(return_value=(chunk for chunk in [first, last]))
    monkeypatch.setattr(llm, "_invoke", provider)

    stream = llm._code_block_mode_wrapper("model", {}, [], {"response_format": "JSON"})
    selected, unused = (
        (fenced, normal) if expected_hook.endswith("backtick") else (normal, fenced)
    )
    selected.assert_called_once()
    unused.assert_not_called()
    assert list(stream) == [result]
    assert received == [
        ("model", provider.call_args.kwargs["prompt_messages"], [first, last])
    ]
    assert llm.started_at == 0
