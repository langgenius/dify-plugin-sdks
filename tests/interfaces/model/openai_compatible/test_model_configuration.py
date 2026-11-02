from decimal import Decimal

import pytest

from dify_plugin.entities.model import ModelFeature, ModelPropertyKey
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessageTool,
    TextPromptMessageContent,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)


@pytest.mark.parametrize("calling_type", ["tool_call", "function_call"])
def test_token_budget_includes_tool_history_and_tool_definitions(
    calling_type: str,
) -> None:
    model = OAICompatLargeLanguageModel([])
    credentials = {"function_calling_type": calling_type}
    prompt = UserPromptMessage(content="What is the weather in Paris?")
    history = [
        prompt,
        AssistantPromptMessage(
            tool_calls=[
                AssistantPromptMessage.ToolCall(
                    id="weather",
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name="weather", arguments='{"city":"Paris"}'
                    ),
                )
            ]
        ),
        ToolPromptMessage(content="It is sunny.", tool_call_id="weather"),
    ]
    minimal_tool = PromptMessageTool(
        name="weather", description="", parameters={"type": "object"}
    )
    tool = PromptMessageTool(
        name="weather",
        description="Get the current weather for a city.",
        parameters={
            "title": "Weather input",
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "The city to look up."},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    )

    prompt_tokens = model.get_num_tokens("model", credentials, [prompt])
    history_tokens = model.get_num_tokens("model", credentials, history)
    minimal_tool_tokens = model.get_num_tokens(
        "model", credentials, history, [minimal_tool]
    )
    full_tool_tokens = model.get_num_tokens("model", credentials, history, [tool])

    assert prompt_tokens < history_tokens < minimal_tool_tokens < full_tool_tokens
    assert (
        model.get_num_tokens("model", credentials, history, [tool, minimal_tool])
        > full_tool_tokens
    )


def test_token_budget_counts_names_and_text_without_encoding_image_urls() -> None:
    model = OAICompatLargeLanguageModel([])
    prompt = UserPromptMessage(content="Describe this image")
    image = ImagePromptMessageContent(
        format="png", mime_type="image/png", url="https://example.com/image.png"
    )
    image_prompt = UserPromptMessage(
        content=[TextPromptMessageContent(data="Describe this image"), image]
    )
    text_tokens = model.get_num_tokens("model", {}, [prompt])
    image_tokens = model.get_num_tokens("model", {}, [image_prompt])
    long_url_prompt = image_prompt.model_copy(deep=True)
    long_url_prompt.content[1].url += "?signature=" + "a" * 10_000

    assert model.get_num_tokens("model", {}, [long_url_prompt]) == image_tokens
    assert image_tokens >= text_tokens
    prompt.name = "planner"
    assert model.get_num_tokens("model", {}, [prompt]) > text_tokens


@pytest.mark.parametrize(
    ("calling_type", "media", "stream_tools", "features"),
    [
        (
            "function_call",
            "support",
            "supported",
            {
                ModelFeature.TOOL_CALL,
                ModelFeature.STREAM_TOOL_CALL,
                ModelFeature.VISION,
                ModelFeature.VIDEO,
            },
        ),
        ("tool_call", "not_support", "not_supported", {ModelFeature.MULTI_TOOL_CALL}),
        ("no_call", "not_support", "not_supported", set()),
    ],
)
def test_custom_model_capabilities_and_limits_follow_credentials(
    calling_type: str, media: str, stream_tools: str, features: set[ModelFeature]
) -> None:
    schema = OAICompatLargeLanguageModel([]).get_model_schema(
        "custom-model",
        {
            "mode": "chat",
            "function_calling_type": calling_type,
            "vision_support": media,
            "video_support": media,
            "stream_function_calling": stream_tools,
            "context_size": "32768",
            "max_tokens_to_sample": "2048",
            "input_price": "2.5",
            "output_price": "5",
            "unit": "0.001",
        },
    )
    assert schema is not None
    assert set(schema.features or []) == features
    assert schema.model_properties[ModelPropertyKey.CONTEXT_SIZE] == 32768
    max_tokens = next(
        rule for rule in schema.parameter_rules if rule.name == "max_tokens"
    )
    assert max_tokens.max == 2048
    assert schema.pricing is not None
    assert schema.pricing.input == Decimal("2.5")
    assert schema.pricing.output == Decimal(5)


def test_embedding_token_estimates_preserve_input_order_and_empty_texts() -> None:
    model = OAICompatEmbeddingModel([])
    assert model.get_num_tokens("model", {}, ["Hello", "", "Hello world"]) == [1, 0, 2]


def test_large_prompts_have_positive_nondecreasing_token_estimates() -> None:
    model = OAICompatLargeLanguageModel([])

    counts = [
        model.get_num_tokens("model", {}, [UserPromptMessage(content="a" * size)])
        for size in (100_000, 200_000)
    ]

    assert all(type(count) is int and count > 0 for count in counts)
    assert counts[1] >= counts[0]


@pytest.mark.parametrize(
    "parameter",
    [
        {"type": "string", "enum": ["fast", "accurate"]},
        {"type": "integer", "enum": [1, 2]},
        {"type": "boolean", "enum": [True, False]},
        {"type": ["string", "null"], "enum": ["automatic", None]},
    ],
    ids=["string", "integer", "boolean", "nullable"],
)
def test_token_budget_accepts_json_schema_enum_values(parameter: dict) -> None:
    model = OAICompatLargeLanguageModel([])
    prompts = [UserPromptMessage(content="Choose a setting")]
    tool = PromptMessageTool(
        name="configure",
        description="Configure the setting",
        parameters={
            "type": "object",
            "properties": {"setting": parameter},
            "required": ["setting"],
        },
    )

    assert model.get_num_tokens("model", {}, prompts, [tool]) > model.get_num_tokens(
        "model", {}, prompts
    )


def test_token_budget_counts_nested_schema_content() -> None:
    model = OAICompatLargeLanguageModel([])
    prompts = [UserPromptMessage(content="Configure the input")]
    tool = PromptMessageTool(
        name="configure",
        description="Configure the input",
        parameters={"allOf": [{"type": "object"}]},
    )
    baseline = model.get_num_tokens("model", {}, prompts, [tool])
    tool.parameters["allOf"][0]["description"] = (
        "A detailed explanation of the input. " * 100
    )

    assert model.get_num_tokens("model", {}, prompts, [tool]) > baseline + 100


def test_invalid_custom_model_mode_reports_a_configuration_error() -> None:
    with pytest.raises(ValueError, match="invalid-mode"):
        OAICompatLargeLanguageModel([]).get_model_schema(
            "model", {"mode": "invalid-mode"}
        )
