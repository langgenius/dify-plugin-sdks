import inspect
import logging
import math
import time
from abc import abstractmethod
from collections.abc import Callable, Generator, Mapping
from contextlib import closing
from typing import Literal
from xml.parsers import expat

from pydantic import ConfigDict, JsonValue

from dify_plugin.entities.model import (
    ModelFeature,
    ModelPropertyKey,
    ModelType,
    ParameterRule,
    ParameterType,
    PriceType,
)
from dify_plugin.entities.model.llm import (
    LLMMode,
    LLMPollingResult,
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageContentType,
    PromptMessageTool,
    SystemPromptMessage,
    UserPromptMessage,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.ai_model import AIModel

logger = logging.getLogger(__name__)

CODE_FENCE_BACKTICK_COUNT = 3
STRUCTURED_RESPONSE_FORMATS = frozenset({"JSON", "XML"})


def _xml_code_fence_filter() -> Callable[[str, bool], str]:
    parser = expat.ParserCreate()
    depth = 0
    root_closed = False
    pending = bytearray()
    offset = position = 0
    line_start = True
    failed = done = False

    def start(_name: str, _attributes: dict[str, str]) -> None:
        nonlocal depth
        depth += 1

    def end(_name: str) -> None:
        nonlocal depth, root_closed
        depth -= 1
        root_closed = depth == 0

    parser.StartElementHandler = start
    parser.EndElementHandler = end

    def feed(char: str, final: bool) -> str:
        nonlocal pending, offset, position, line_start, failed, done
        if done:
            return ""
        data = char.encode()
        position += len(data)
        if not failed:
            try:
                parser.Parse(char, final)
            except expat.ExpatError:
                failed = True
        if not pending and not (line_start and char == "`"):
            line_start = char == "\n"
            return char
        if not pending:
            offset = position - len(data)
        pending += data
        # Expat can defer parsing; retain fence candidates until it consumes them.
        consumed = max(0, parser.CurrentByteIndex - offset)
        safe = bytearray()
        if consumed:
            safe, pending = pending[:consumed], pending[consumed:]
            line_start, offset = safe.endswith(b"\n"), offset + len(safe)
        if failed:
            if root_closed and parser.ErrorByteIndex == offset and line_start:
                if pending.startswith(b"```"):
                    done = True
                    return safe.decode()
                if not final and bytes(pending) in {b"`", b"``"}:
                    return safe.decode()
            safe += pending
            line_start, pending = pending.endswith(b"\n"), bytearray()
        elif final:
            safe += pending
            pending = bytearray()
        return safe.decode()

    return feed


class LargeLanguageModel(AIModel):
    """Model class for large language model."""

    model_type: ModelType = ModelType.LLM

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator[LLMResultChunk, None, None]:
        """Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :return: full response or stream response chunk generator result
        """
        raise NotImplementedError

    def _start_polling(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[False] = False,
        user: str | None = None,
        *,
        json_schema: dict[str, JsonValue] | None = None,
    ) -> LLMPollingResult:
        """Start a polling-based large language model invocation."""
        del (
            model,
            credentials,
            prompt_messages,
            model_parameters,
            tools,
            stop,
            stream,
            user,
            json_schema,
        )
        raise NotImplementedError

    def _check_polling(
        self,
        model: str,
        credentials: dict,
        plugin_state: dict[str, JsonValue],
        user: str | None = None,
    ) -> LLMPollingResult:
        """Check a polling-based large language model invocation."""
        del model, credentials, plugin_state, user
        raise NotImplementedError

    @abstractmethod
    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        """Get number of tokens for given prompt messages

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param tools: tools for tool calling
        :return:
        """
        raise NotImplementedError

    ############################################################
    #            For plugin implementation use only            #
    ############################################################

    def enforce_stop_tokens(self, text: str, stop: list[str]) -> str:
        """Cut off the text as soon as any stop words occur."""
        for sequence in stop:
            index = text.find(sequence)
            if index >= 0:
                text = text[:index]
        return text

    def get_parameter_rules(self, model: str, credentials: dict) -> list[ParameterRule]:
        """Get parameter rules

        :param model: model name
        :param credentials: model credentials
        :return: parameter rules

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)
        if model_schema:
            return model_schema.parameter_rules

        return []

    def get_model_mode(self, model: str, credentials: Mapping | None = None) -> LLMMode:
        """Get model mode

        :param model: model name
        :param credentials: model credentials
        :return: model mode

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)

        mode = LLMMode.CHAT
        if model_schema and model_schema.model_properties.get(ModelPropertyKey.MODE):
            mode = LLMMode.value_of(
                model_schema.model_properties[ModelPropertyKey.MODE],
            )

        return mode

    def supports_polling(self, model: str, credentials: Mapping | None = None) -> bool:
        model_schema = self.get_model_schema(model, credentials)
        has_feature = bool(
            model_schema
            and model_schema.features
            and ModelFeature.POLLING in model_schema.features
        )
        base_start_polling = inspect.getattr_static(
            LargeLanguageModel,
            "_start_polling",
        )
        base_check_polling = inspect.getattr_static(
            LargeLanguageModel,
            "_check_polling",
        )
        start_polling = inspect.getattr_static(type(self), "_start_polling")
        check_polling = inspect.getattr_static(type(self), "_check_polling")
        has_methods = (
            start_polling is not base_start_polling
            and check_polling is not base_check_polling
        )

        return has_feature and has_methods

    def _calc_response_usage(
        self,
        model: str,
        credentials: dict,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> LLMUsage:
        """Calculate response usage

        :param model: model name
        :param credentials: model credentials
        :param prompt_tokens: prompt tokens
        :param completion_tokens: completion tokens
        :return: usage

        Returns:
            The return value.
        """
        # get prompt price info
        prompt_price_info = self.get_price(
            model=model,
            credentials=credentials,
            price_type=PriceType.INPUT,
            tokens=prompt_tokens,
        )

        # get completion price info
        completion_price_info = self.get_price(
            model=model,
            credentials=credentials,
            price_type=PriceType.OUTPUT,
            tokens=completion_tokens,
        )

        # Calculate latency from thread-local storage
        current_time = time.perf_counter()
        latency = current_time - self.started_at

        # transform usage
        return LLMUsage(
            prompt_tokens=prompt_tokens,
            prompt_unit_price=prompt_price_info.unit_price,
            prompt_price_unit=prompt_price_info.unit,
            prompt_price=prompt_price_info.total_amount,
            completion_tokens=completion_tokens,
            completion_unit_price=completion_price_info.unit_price,
            completion_price_unit=completion_price_info.unit,
            completion_price=completion_price_info.total_amount,
            total_tokens=prompt_tokens + completion_tokens,
            total_price=prompt_price_info.total_amount
            + completion_price_info.total_amount,
            currency=prompt_price_info.currency,
            latency=latency,
        )

    def _validate_and_filter_model_parameters(
        self,
        model: str,
        model_parameters: dict,
        credentials: dict,
    ) -> dict:
        """Validate model parameters

        :param model: model name
        :param model_parameters: model parameters
        :param credentials: model credentials
        :return:

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        parameter_rules = self.get_parameter_rules(model, credentials)

        # validate model parameters
        filtered_model_parameters = {}
        for parameter_rule in parameter_rules:
            parameter_name = parameter_rule.name
            parameter_value = model_parameters.get(parameter_name)
            if parameter_value is None:
                if (
                    parameter_rule.use_template
                    and parameter_rule.use_template in model_parameters
                ):
                    # if parameter value is None, use template value variable
                    # name instead
                    parameter_value = model_parameters[parameter_rule.use_template]
                elif parameter_rule.required:
                    if parameter_rule.default is None:
                        msg = f"Model Parameter {parameter_name} is required."
                        raise ValueError(msg)
                    parameter_value = parameter_rule.default
                else:
                    continue

            # validate parameter value type
            if parameter_rule.type == ParameterType.INT:
                if isinstance(parameter_value, bool) or not isinstance(
                    parameter_value, int
                ):
                    msg = f"Model Parameter {parameter_name} should be int."
                    raise ValueError(msg)

                # validate parameter value range
                if (
                    parameter_rule.min is not None
                    and parameter_value < parameter_rule.min
                ):
                    msg = (
                        f"Model Parameter {parameter_name} should be greater "
                        f"than or equal to {parameter_rule.min}."
                    )
                    raise ValueError(
                        msg,
                    )

                if (
                    parameter_rule.max is not None
                    and parameter_value > parameter_rule.max
                ):
                    msg = (
                        f"Model Parameter {parameter_name} should be less "
                        f"than or equal to {parameter_rule.max}."
                    )
                    raise ValueError(
                        msg,
                    )
            elif parameter_rule.type == ParameterType.FLOAT:
                if isinstance(parameter_value, bool) or not isinstance(
                    parameter_value, float | int
                ):
                    msg = f"Model Parameter {parameter_name} should be float."
                    raise ValueError(
                        msg,
                    )

                if isinstance(parameter_value, float) and not math.isfinite(
                    parameter_value
                ):
                    msg = f"Model Parameter {parameter_name} should be finite."
                    raise ValueError(msg)

                # validate parameter value precision
                if parameter_rule.precision is not None:
                    if parameter_rule.precision == 0:
                        if parameter_value != int(parameter_value):
                            msg = f"Model Parameter {parameter_name} should be int."
                            raise ValueError(
                                msg,
                            )
                    elif parameter_value != round(
                        parameter_value,
                        parameter_rule.precision,
                    ):
                        msg = (
                            f"Model Parameter {parameter_name} should be round to "
                            f"{parameter_rule.precision} decimal places."
                        )
                        raise ValueError(
                            msg,
                        )

                # validate parameter value range
                if (
                    parameter_rule.min is not None
                    and parameter_value < parameter_rule.min
                ):
                    msg = (
                        f"Model Parameter {parameter_name} should be greater "
                        f"than or equal to {parameter_rule.min}."
                    )
                    raise ValueError(
                        msg,
                    )

                if (
                    parameter_rule.max is not None
                    and parameter_value > parameter_rule.max
                ):
                    msg = (
                        f"Model Parameter {parameter_name} should be less "
                        f"than or equal to {parameter_rule.max}."
                    )
                    raise ValueError(
                        msg,
                    )
            elif parameter_rule.type == ParameterType.BOOLEAN:
                if not isinstance(parameter_value, bool):
                    msg = f"Model Parameter {parameter_name} should be bool."
                    raise ValueError(
                        msg,
                    )
            elif parameter_rule.type == ParameterType.STRING:
                if not isinstance(parameter_value, str):
                    msg = f"Model Parameter {parameter_name} should be string."
                    raise ValueError(
                        msg,
                    )

                # validate options
                if (
                    parameter_rule.options
                    and parameter_value not in parameter_rule.options
                ):
                    msg = (
                        f"Model Parameter {parameter_name} should be one of "
                        f"{parameter_rule.options}."
                    )
                    raise ValueError(
                        msg,
                    )
            elif parameter_rule.type == ParameterType.TEXT:
                if not isinstance(parameter_value, str):
                    msg = f"Model Parameter {parameter_name} should be string."
                    raise ValueError(
                        msg,
                    )
            else:
                msg = (
                    f"Model Parameter {parameter_name} type "
                    f"{parameter_rule.type} is not supported."
                )
                raise ValueError(
                    msg,
                )

            filtered_model_parameters[parameter_name] = parameter_value

        return filtered_model_parameters

    def _code_block_mode_wrapper(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator[LLMResultChunk, None, None]:
        """Code block mode wrapper, ensure the response is a code block with
        output markdown quote

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result

        Returns:
            The return value.
        """
        block_prompts = (
            "You should always follow the instructions and output a valid "
            "{{block}} object.\n"
            "The structure of the {{block}} object you can found in the "
            'instructions, use {"answer": "$your_answer"} as the default '
            "structure\n"
            "if you are not sure about the structure.\n"
            "\n"
            "<instructions>\n"
            "{{instructions}}\n"
            "</instructions>\n"
        )

        code_block = model_parameters.get("response_format", "")
        if not code_block:
            return self._invoke(
                model=model,
                credentials=credentials,
                prompt_messages=prompt_messages,
                model_parameters=model_parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                user=user,
            )

        prompt_messages = [message.model_copy(deep=True) for message in prompt_messages]
        model_parameters = model_parameters.copy()
        model_parameters.pop("response_format")
        stop = list(stop or [])
        if code_block == "JSON":
            stop.extend(["\n```", "```\n"])
        block_prompts = block_prompts.replace("{{block}}", code_block)

        # check if there is a system message
        if len(prompt_messages) > 0 and isinstance(
            prompt_messages[0],
            SystemPromptMessage,
        ):
            # override the system message
            prompt_messages[0] = SystemPromptMessage(
                content=block_prompts.replace(
                    "{{instructions}}",
                    str(prompt_messages[0].content),
                ),
            )
        else:
            # insert the system message
            prompt_messages.insert(
                0,
                SystemPromptMessage(
                    content=block_prompts.replace(
                        "{{instructions}}",
                        f"Please output a valid {code_block} object.",
                    ),
                ),
            )

        if len(prompt_messages) > 0 and isinstance(
            prompt_messages[-1],
            UserPromptMessage,
        ):
            # add ```JSON\n to the last text message
            if isinstance(prompt_messages[-1].content, str):
                prompt_messages[-1].content += f"\n```{code_block}\n"
            elif isinstance(prompt_messages[-1].content, list):
                for i in range(len(prompt_messages[-1].content) - 1, -1, -1):
                    if (
                        prompt_messages[-1].content[i].type
                        == PromptMessageContentType.TEXT
                    ):
                        prompt_messages[-1].content[i].data += f"\n```{code_block}\n"
                        break
        else:
            # append a user message
            prompt_messages.append(UserPromptMessage(content=f"```{code_block}\n"))

        response = self._invoke(
            model=model,
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            user=user,
        )

        if isinstance(response, Generator):

            def process_response() -> Generator[LLMResultChunk, None, None]:
                with closing(response):
                    yield from self._code_block_mode_stream_processor(
                        model=model,
                        prompt_messages=prompt_messages,
                        input_generator=response,
                    )

            return process_response()

        return response

    def _code_block_mode_stream_processor(
        self,
        model: str,
        prompt_messages: list[PromptMessage],
        input_generator: Generator[LLMResultChunk, None, None],
    ) -> Generator[LLMResultChunk, None, None]:
        """Strip outer code fences while preserving streamed content and metadata.

        :param model: model name
        :param prompt_messages: prompt messages
        :param input_generator: input generator
        :return: output generator

        Yields:
            Generated values.
        """
        del prompt_messages
        state = "start"
        backtick_count = 0
        at_line_start = True
        body_started = False
        xml_filter = None
        for chunk in input_generator:
            content = chunk.delta.message.get_text_content()
            if not content:
                if xml_filter is not None and chunk.delta.finish_reason is not None:
                    remaining = xml_filter("", True)
                    if remaining:
                        yield LLMResultChunk(
                            model=model,
                            delta=LLMResultChunkDelta(
                                index=0,
                                message=AssistantPromptMessage(content=remaining),
                            ),
                        )
                yield chunk
                continue
            chunk.delta.message.content = ""
            yield chunk
            new_piece: str = ""
            for char in content:
                if state == "done":
                    break
                if state == "opening_fence":
                    if char == "\n":
                        state = "content"
                    continue
                if state == "start":
                    if char == "`":
                        backtick_count += 1
                        if backtick_count == CODE_FENCE_BACKTICK_COUNT:
                            state = "opening_fence"
                            backtick_count = 0
                        continue
                    if not backtick_count and char.isspace():
                        new_piece += char
                        continue
                    state = "content"
                if not body_started and not char.isspace():
                    body_started = True
                    if char in {"<", "\ufeff"}:
                        xml_filter = _xml_code_fence_filter()
                if xml_filter is not None:
                    new_piece += xml_filter(char, False)
                    continue
                if at_line_start and char == "`":
                    backtick_count += 1
                    if backtick_count == CODE_FENCE_BACKTICK_COUNT:
                        state = "done"
                        backtick_count = 0
                    continue
                new_piece += "`" * backtick_count + char
                backtick_count = 0
                at_line_start = char == "\n"

            if new_piece:
                yield LLMResultChunk(
                    model=model,
                    delta=LLMResultChunkDelta(
                        index=0,
                        message=AssistantPromptMessage(
                            content=new_piece,
                            tool_calls=[],
                        ),
                    ),
                )

        remaining = (
            xml_filter("", True) if xml_filter is not None else "`" * backtick_count
        )
        if remaining:
            yield LLMResultChunk(
                model=model,
                delta=LLMResultChunkDelta(
                    index=0,
                    message=AssistantPromptMessage(content=remaining),
                ),
            )

    def _wrap_thinking_by_reasoning_content(
        self,
        delta: dict,
        is_reasoning: bool,
    ) -> tuple[str, bool]:
        """Wrap streamed reasoning content with HTML think tags.

        :param delta: delta dictionary from LLM streaming response
        :param is_reasoning: is reasoning
        :return: tuple of (processed_content, is_reasoning)

        Returns:
            The return value.
        """
        content = delta.get("content") or ""
        reasoning_content = delta.get("reasoning_content") or delta.get("reasoning")
        output = content
        if reasoning_content:
            if not is_reasoning:
                output = "<think>\n" + reasoning_content
                is_reasoning = True
            else:
                output = reasoning_content
            if content or delta.get("tool_calls") or delta.get("function_call"):
                is_reasoning = False
                output += "\n</think>" + content
        elif is_reasoning:
            is_reasoning = False
            output = "\n</think>" + content

        return output, is_reasoning

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def start_polling(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict | None = None,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[False] = False,
        user: str | None = None,
        json_schema: dict[str, JsonValue] | None = None,
    ) -> LLMPollingResult:
        """Start a polling-based large language model invocation."""
        if not self.supports_polling(model, credentials):
            msg = f"Model `{model}` does not support polling."
            raise NotImplementedError(msg)

        if model_parameters is None:
            model_parameters = {}

        model_parameters = self._validate_and_filter_model_parameters(
            model,
            model_parameters,
            credentials,
        )

        with self.timing_context():
            try:
                return self._start_polling(
                    model=model,
                    credentials=credentials,
                    prompt_messages=prompt_messages,
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    user=user,
                    json_schema=json_schema,
                )
            except InvokeError:
                raise
            except Exception as e:
                raise self._transform_invoke_error(e) from e

    def check_polling(
        self,
        model: str,
        credentials: dict,
        plugin_state: dict[str, JsonValue],
        user: str | None = None,
    ) -> LLMPollingResult:
        """Check a polling-based large language model invocation."""
        if not self.supports_polling(model, credentials):
            msg = f"Model `{model}` does not support polling."
            raise NotImplementedError(msg)

        with self.timing_context():
            try:
                return self._check_polling(
                    model=model,
                    credentials=credentials,
                    plugin_state=plugin_state,
                    user=user,
                )
            except InvokeError:
                raise
            except Exception as e:
                raise self._transform_invoke_error(e) from e

    def invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict | None = None,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> Generator[LLMResultChunk, None, None]:
        """Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result

        Yields:
            Generated values.

        Raises:
            InvokeError: If invoking the model or reading its response fails.
        """
        # validate and filter model parameters
        if model_parameters is None:
            model_parameters = {}

        model_parameters = self._validate_and_filter_model_parameters(
            model,
            model_parameters,
            credentials,
        )

        with self.timing_context():
            invoke = (
                self._code_block_mode_wrapper
                if "response_format" in model_parameters
                and model_parameters["response_format"] in STRUCTURED_RESPONSE_FORMATS
                else self._invoke
            )
            try:
                result = invoke(
                    model=model,
                    credentials=credentials,
                    prompt_messages=prompt_messages,
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    user=user,
                )
                if isinstance(result, LLMResult):
                    yield result.to_llm_result_chunk()
                else:
                    # NOTE: `yield from` cannot been replaced by `return`
                    # because of `timing_context`
                    yield from result
            except InvokeError:
                raise
            except Exception as e:
                raise self._transform_invoke_error(e) from e
