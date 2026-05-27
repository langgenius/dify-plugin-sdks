import json
import logging
import pathlib
import time
from collections.abc import Generator
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

from pydantic import BaseModel

from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.entities.model import ModelFeature
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultChunk,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageContentType,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.entities.provider_config import LogMetadata
from dify_plugin.entities.tool import ToolInvokeMessage, ToolProviderType
from dify_plugin.interfaces.agent import (
    AgentModelConfig,
    AgentStrategy,
    ToolEntity,
    ToolInvokeMeta,
)

logger = logging.getLogger(__name__)
EMPTY_STRING = ""
IMAGE_RESPONSE_TYPES = frozenset({
    ToolInvokeMessage.MessageType.IMAGE_LINK,
    ToolInvokeMessage.MessageType.IMAGE,
})
ToolCall = tuple[str, str, dict[str, Any]]


@dataclass
class FunctionCallingRoundResult:
    response: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_names: str = ""
    current_llm_usage: LLMUsage | None = None
    function_call_state: bool = False


class FunctionCallingParams(BaseModel):
    query: str
    instruction: str | None
    model: AgentModelConfig
    tools: list[ToolEntity] | None
    maximum_iterations: int = 3


class FunctionCallingAgentStrategy(AgentStrategy):
    query: str = ""
    instruction: str | None = ""

    @property
    def _user_prompt_message(self) -> UserPromptMessage:
        return UserPromptMessage(content=self.query)

    @property
    def _system_prompt_message(self) -> SystemPromptMessage:
        return SystemPromptMessage(content=self.instruction)

    def _invoke(
        self,
        parameters: dict[str, Any],
    ) -> Generator[AgentInvokeMessage, None, None]:
        """Run FunctionCall agent application"""
        fc_params = FunctionCallingParams(**parameters)

        # init prompt messages
        query = fc_params.query
        self.query = query
        self.instruction = fc_params.instruction
        history_prompt_messages = fc_params.model.history_prompt_messages
        history_prompt_messages.insert(0, self._system_prompt_message)
        history_prompt_messages.append(self._user_prompt_message)

        # convert tool messages
        tools = fc_params.tools
        tool_instances = {tool.identity.name: tool for tool in tools} if tools else {}
        prompt_messages_tools = self._init_prompt_tools(tools)

        # init model parameters
        stream = (
            ModelFeature.STREAM_TOOL_CALL in fc_params.model.entity.features
            if fc_params.model.entity and fc_params.model.entity.features
            else False
        )
        model = fc_params.model
        stop = (
            fc_params.model.completion_params.get("stop", [])
            if fc_params.model.completion_params
            else []
        )

        # init function calling state
        iteration_step = 1
        max_iteration_steps = fc_params.maximum_iterations
        current_thoughts: list[PromptMessage] = []
        function_call_state = True  # continue to run until there is not any tool call
        llm_usage: dict[str, LLMUsage | None] = {"usage": None}
        final_answer = ""

        while function_call_state and iteration_step <= max_iteration_steps:
            # start a new round
            function_call_state = False
            round_started_at = time.perf_counter()
            round_log = self.create_log_message(
                label=f"ROUND {iteration_step}",
                data={},
                metadata={
                    LogMetadata.STARTED_AT: round_started_at,
                },
                status=ToolInvokeMessage.LogMessage.LogStatus.START,
            )
            yield round_log

            # If max_iteration_steps=1, need to execute tool calls
            if iteration_step == max_iteration_steps and max_iteration_steps > 1:
                # the last iteration, remove all tools
                prompt_messages_tools = []

            # recalc llm max tokens
            prompt_messages = self._organize_prompt_messages(
                history_prompt_messages=history_prompt_messages,
                current_thoughts=current_thoughts,
            )
            if model.entity and model.completion_params:
                self.recalc_llm_max_tokens(
                    model.entity,
                    prompt_messages,
                    model.completion_params,
                )
            # invoke model
            model_started_at = time.perf_counter()
            model_log = self.create_log_message(
                label=f"{model.model} Thought",
                data={},
                metadata={
                    LogMetadata.STARTED_AT: model_started_at,
                    LogMetadata.PROVIDER: model.provider,
                },
                parent=round_log,
                status=ToolInvokeMessage.LogMessage.LogStatus.START,
            )
            yield model_log
            model_config = LLMModelConfig(**model.model_dump(mode="json"))
            chunks: Generator[LLMResultChunk, None, None] | LLMResult = (
                self.session.model.llm.invoke(
                    model_config=model_config,
                    prompt_messages=prompt_messages,
                    stop=stop,
                    stream=stream,
                    tools=prompt_messages_tools,
                )
            )

            round_result = FunctionCallingRoundResult()
            yield from self._process_model_response(
                chunks=chunks,
                iteration_step=iteration_step,
                max_iteration_steps=max_iteration_steps,
                llm_usage=llm_usage,
                round_result=round_result,
            )
            function_call_state = round_result.function_call_state
            tool_calls = round_result.tool_calls
            tool_call_names = round_result.tool_call_names
            response = round_result.response
            current_llm_usage = round_result.current_llm_usage

            yield self.finish_log_message(
                log=model_log,
                data={
                    "output": response,
                    "tool_name": tool_call_names,
                    "tool_input": [
                        {"name": tool_call[1], "args": tool_call[2]}
                        for tool_call in tool_calls
                    ],
                },
                metadata={
                    LogMetadata.STARTED_AT: model_started_at,
                    LogMetadata.FINISHED_AT: time.perf_counter(),
                    LogMetadata.ELAPSED_TIME: time.perf_counter() - model_started_at,
                    LogMetadata.PROVIDER: model.provider,
                    LogMetadata.TOTAL_PRICE: current_llm_usage.total_price
                    if current_llm_usage
                    else 0,
                    LogMetadata.CURRENCY: current_llm_usage.currency
                    if current_llm_usage
                    else "",
                    LogMetadata.TOTAL_TOKENS: current_llm_usage.total_tokens
                    if current_llm_usage
                    else 0,
                },
            )
            assistant_message = AssistantPromptMessage(content="", tool_calls=[])
            if not tool_calls:
                assistant_message.content = response
                current_thoughts.append(assistant_message)

            final_answer += response + "\n"

            # call tools
            tool_responses = []
            for tool_call_id, tool_call_name, tool_call_args in tool_calls:
                current_thoughts.append(
                    AssistantPromptMessage(
                        content="",
                        tool_calls=[
                            AssistantPromptMessage.ToolCall(
                                id=tool_call_id,
                                type="function",
                                function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                                    name=tool_call_name,
                                    arguments=json.dumps(
                                        tool_call_args,
                                        ensure_ascii=False,
                                    ),
                                ),
                            ),
                        ],
                    ),
                )
                tool_instance = tool_instances[tool_call_name]
                tool_call_started_at = time.perf_counter()
                tool_call_log = self.create_log_message(
                    label=f"CALL {tool_call_name}",
                    data={},
                    metadata={
                        LogMetadata.STARTED_AT: time.perf_counter(),
                        LogMetadata.PROVIDER: tool_instance.identity.provider,
                    },
                    parent=round_log,
                    status=ToolInvokeMessage.LogMessage.LogStatus.START,
                )
                yield tool_call_log
                tool_response = {}
                yield from self._invoke_tool_call(
                    tool_instance=tool_instance,
                    tool_call_id=tool_call_id,
                    tool_call_name=tool_call_name,
                    tool_call_args=tool_call_args,
                    tool_response=tool_response,
                )

                yield self.finish_log_message(
                    log=tool_call_log,
                    data={
                        "output": tool_response,
                    },
                    metadata={
                        LogMetadata.STARTED_AT: tool_call_started_at,
                        LogMetadata.PROVIDER: tool_instance.identity.provider,
                        LogMetadata.FINISHED_AT: time.perf_counter(),
                        LogMetadata.ELAPSED_TIME: time.perf_counter()
                        - tool_call_started_at,
                    },
                )
                tool_responses.append(tool_response)
                if tool_response["tool_response"] is not None:
                    current_thoughts.append(
                        ToolPromptMessage(
                            content=str(tool_response["tool_response"]),
                            tool_call_id=tool_call_id,
                            name=tool_call_name,
                        ),
                    )

            # update prompt tool
            for prompt_tool in prompt_messages_tools:
                self.update_prompt_message_tool(
                    tool_instances[prompt_tool.name],
                    prompt_tool,
                )
            yield self.finish_log_message(
                log=round_log,
                data={
                    "output": {
                        "llm_response": response,
                        "tool_responses": tool_responses,
                    },
                },
                metadata={
                    LogMetadata.STARTED_AT: round_started_at,
                    LogMetadata.FINISHED_AT: time.perf_counter(),
                    LogMetadata.ELAPSED_TIME: time.perf_counter() - round_started_at,
                    LogMetadata.TOTAL_PRICE: current_llm_usage.total_price
                    if current_llm_usage
                    else 0,
                    LogMetadata.CURRENCY: current_llm_usage.currency
                    if current_llm_usage
                    else "",
                    LogMetadata.TOTAL_TOKENS: current_llm_usage.total_tokens
                    if current_llm_usage
                    else 0,
                },
            )
            # If max_iteration_steps=1, need to return tool responses
            if tool_responses and max_iteration_steps == 1:
                for resp in tool_responses:
                    yield self.create_text_message(str(resp["tool_response"]))
            iteration_step += 1
        yield self.create_json_message({
            "execution_metadata": {
                LogMetadata.TOTAL_PRICE: llm_usage["usage"].total_price
                if llm_usage["usage"] is not None
                else 0,
                LogMetadata.CURRENCY: llm_usage["usage"].currency
                if llm_usage["usage"] is not None
                else "",
                LogMetadata.TOTAL_TOKENS: llm_usage["usage"].total_tokens
                if llm_usage["usage"] is not None
                else 0,
            },
        })

    def _process_model_response(
        self,
        chunks: Generator[LLMResultChunk, None, None] | LLMResult,
        iteration_step: int,
        max_iteration_steps: int,
        llm_usage: dict[str, LLMUsage | None],
        round_result: FunctionCallingRoundResult,
    ) -> Generator[AgentInvokeMessage, None, None]:
        if isinstance(chunks, Generator):
            yield from self._process_stream_response(
                chunks=chunks,
                iteration_step=iteration_step,
                max_iteration_steps=max_iteration_steps,
                llm_usage=llm_usage,
                round_result=round_result,
            )
            return

        yield from self._process_blocking_response(
            result=cast("LLMResult", chunks),
            llm_usage=llm_usage,
            round_result=round_result,
        )

    def _process_stream_response(
        self,
        chunks: Generator[LLMResultChunk, None, None],
        iteration_step: int,
        max_iteration_steps: int,
        llm_usage: dict[str, LLMUsage | None],
        round_result: FunctionCallingRoundResult,
    ) -> Generator[AgentInvokeMessage, None, None]:
        for chunk in chunks:
            if self.check_tool_calls(chunk):
                round_result.function_call_state = True
                round_result.tool_calls.extend(self.extract_tool_calls(chunk) or [])

            if chunk.delta.message and chunk.delta.message.content:
                yield from self._stream_text_messages(
                    chunk.delta.message.content,
                    should_yield=(
                        not round_result.function_call_state
                        or iteration_step == max_iteration_steps
                    ),
                    round_result=round_result,
                )

            if chunk.delta.usage:
                self.increase_usage(llm_usage, chunk.delta.usage)
                round_result.current_llm_usage = chunk.delta.usage

        round_result.tool_call_names = self._format_tool_call_names(
            round_result.tool_calls,
        )

    def _stream_text_messages(
        self,
        content: object,
        should_yield: bool,
        round_result: FunctionCallingRoundResult,
    ) -> Generator[AgentInvokeMessage, None, None]:
        if isinstance(content, list):
            for content_part in content:
                round_result.response += content_part.data
                if should_yield:
                    yield self.create_text_message(content_part.data)
            return

        text = str(content)
        round_result.response += text
        if should_yield:
            yield self.create_text_message(text)

    def _process_blocking_response(
        self,
        result: LLMResult,
        llm_usage: dict[str, LLMUsage | None],
        round_result: FunctionCallingRoundResult,
    ) -> Generator[AgentInvokeMessage, None, None]:
        if self.check_blocking_tool_calls(result):
            round_result.function_call_state = True
            round_result.tool_calls.extend(
                self.extract_blocking_tool_calls(result) or []
            )

        if result.usage:
            self.increase_usage(llm_usage, result.usage)
            round_result.current_llm_usage = result.usage

        round_result.response = self._message_content_to_text(result.message.content)
        if not result.message.content:
            result.message.content = ""

        yield from self._blocking_text_messages(result.message.content)
        round_result.tool_call_names = self._format_tool_call_names(
            round_result.tool_calls,
        )

    def _message_content_to_text(self, content: object) -> str:
        if isinstance(content, list):
            return "".join(item.data for item in content)
        if content:
            return str(content)
        return ""

    def _blocking_text_messages(
        self,
        content: object,
    ) -> Generator[AgentInvokeMessage, None, None]:
        if isinstance(content, str):
            yield self.create_text_message(content)
        elif isinstance(content, list):
            for content_part in content:
                yield self.create_text_message(content_part.data)

    def _format_tool_call_names(self, tool_calls: list[ToolCall]) -> str:
        return ";".join([tool_call[1] for tool_call in tool_calls])

    def _invoke_tool_call(
        self,
        tool_instance: ToolEntity,
        tool_call_id: str,
        tool_call_name: str,
        tool_call_args: dict[str, Any],
        tool_response: dict,
    ) -> Generator[AgentInvokeMessage, None, None]:
        if not tool_instance:
            tool_response.update({
                "tool_call_id": tool_call_id,
                "tool_call_name": tool_call_name,
                "tool_response": f"there is not a tool named {tool_call_name}",
                "meta": ToolInvokeMeta.error_instance(
                    f"there is not a tool named {tool_call_name}",
                ).to_dict(),
            })
            return

        try:
            tool_invoke_responses = self.session.tool.invoke(
                provider_type=ToolProviderType(tool_instance.provider_type),
                provider=tool_instance.identity.provider,
                tool_name=tool_instance.identity.name,
                parameters={
                    **tool_instance.runtime_parameters,
                    **tool_call_args,
                },
                credential_id=tool_instance.credential_id,
            )
            tool_result = ""
            for tool_invoke_response in tool_invoke_responses:
                text_parts: list[str] = []
                yield from self._append_tool_invoke_response_text(
                    tool_invoke_response,
                    text_parts,
                )
                tool_result += "".join(text_parts)
        except Exception as e:
            tool_result = f"tool invoke error: {e!s}"

        tool_response.update({
            "tool_call_id": tool_call_id,
            "tool_call_name": tool_call_name,
            "tool_call_input": {
                **tool_instance.runtime_parameters,
                **tool_call_args,
            },
            "tool_response": tool_result,
        })

    def _append_tool_invoke_response_text(
        self,
        tool_invoke_response: ToolInvokeMessage,
        text_parts: list[str],
    ) -> Generator[AgentInvokeMessage, None, None]:
        if tool_invoke_response.type == ToolInvokeMessage.MessageType.TEXT:
            text_parts.append(
                cast(
                    "ToolInvokeMessage.TextMessage",
                    tool_invoke_response.message,
                ).text,
            )
            return

        if tool_invoke_response.type == ToolInvokeMessage.MessageType.LINK:
            text = cast(
                "ToolInvokeMessage.TextMessage",
                tool_invoke_response.message,
            ).text
            text_parts.append(f"result link: {text}. please tell user to check it.")
            return

        if tool_invoke_response.type in IMAGE_RESPONSE_TYPES:
            yield from self._handle_image_tool_response(
                tool_invoke_response, text_parts
            )
            return

        if tool_invoke_response.type == ToolInvokeMessage.MessageType.JSON:
            text = json.dumps(
                cast(
                    "ToolInvokeMessage.JsonMessage",
                    tool_invoke_response.message,
                ).json_object,
                ensure_ascii=False,
            )
            text_parts.append(f"tool response: {text}.")
            return

        if tool_invoke_response.type == ToolInvokeMessage.MessageType.BLOB:
            # Conversion to an agent invoke message remains open here.
            yield tool_invoke_response
            text_parts.append("Generated file ... ")
            return

        text_parts.append(f"tool response: {tool_invoke_response.message!r}.")

    def _handle_image_tool_response(
        self,
        tool_invoke_response: ToolInvokeMessage,
        text_parts: list[str],
    ) -> Generator[AgentInvokeMessage, None, None]:
        if hasattr(tool_invoke_response.message, "text"):
            file_info = cast(
                "ToolInvokeMessage.TextMessage",
                tool_invoke_response.message,
            ).text
            yield from self._create_image_blob_message(file_info)

        # Conversion to an agent invoke message remains open here.
        yield tool_invoke_response
        text_parts.append(
            "image has been created and sent to user already, "
            "you do not need to create it, just tell the user to check it now."
        )

    def _create_image_blob_message(
        self,
        file_info: str,
    ) -> Generator[AgentInvokeMessage, None, None]:
        try:
            file_path = pathlib.Path(file_info)
            if not (file_info.startswith("/files/") and file_path.exists()):
                return

            yield self.create_blob_message(
                blob=file_path.read_bytes(),
                meta={
                    "mime_type": "image/png",
                    "filename": file_path.name,
                },
            )
        except Exception:
            logger.exception("Failed to create blob message")

    def check_tool_calls(self, llm_result_chunk: LLMResultChunk) -> bool:
        """Check if there is any tool call in llm result chunk"""
        return bool(llm_result_chunk.delta.message.tool_calls)

    def check_blocking_tool_calls(self, llm_result: LLMResult) -> bool:
        """Check if there is any blocking tool call in llm result"""
        return bool(llm_result.message.tool_calls)

    def extract_tool_calls(
        self,
        llm_result_chunk: LLMResultChunk,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Extract tool calls from llm result chunk

        Returns:
            List[Tuple[str, str, Dict[str, Any]]]:
                [(tool_call_id, tool_call_name, tool_call_args)]

        """
        tool_calls = []
        for prompt_message in llm_result_chunk.delta.message.tool_calls:
            args = {}
            if prompt_message.function.arguments != EMPTY_STRING:
                args = json.loads(prompt_message.function.arguments)

            tool_calls.append((
                prompt_message.id,
                prompt_message.function.name,
                args,
            ))

        return tool_calls

    def extract_blocking_tool_calls(
        self,
        llm_result: LLMResult,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Extract blocking tool calls from llm result

        Returns:
            List[Tuple[str, str, Dict[str, Any]]]:
                [(tool_call_id, tool_call_name, tool_call_args)]

        """
        tool_calls = []
        for prompt_message in llm_result.message.tool_calls:
            args = {}
            if prompt_message.function.arguments != EMPTY_STRING:
                args = json.loads(prompt_message.function.arguments)

            tool_calls.append((
                prompt_message.id,
                prompt_message.function.name,
                args,
            ))

        return tool_calls

    def _init_system_message(
        self,
        prompt_template: str,
        prompt_messages: list[PromptMessage],
    ) -> list[PromptMessage]:
        """Initialize system message"""
        if not prompt_messages and prompt_template:
            return [
                SystemPromptMessage(content=prompt_template),
            ]

        if (
            prompt_messages
            and not isinstance(prompt_messages[0], SystemPromptMessage)
            and prompt_template
        ):
            prompt_messages.insert(0, SystemPromptMessage(content=prompt_template))

        return prompt_messages or []

    def _clear_user_prompt_image_messages(
        self,
        prompt_messages: list[PromptMessage],
    ) -> list[PromptMessage]:
        """As for now, gpt supports both fc and vision at the first iteration.
        We need to remove image messages from the prompt messages at the
        first iteration.

        Returns:
            The return value.
        """
        prompt_messages = deepcopy(prompt_messages)

        for prompt_message in prompt_messages:
            if isinstance(prompt_message, UserPromptMessage) and isinstance(
                prompt_message.content,
                list,
            ):
                prompt_message.content = "\n".join([
                    content.data
                    if content.type == PromptMessageContentType.TEXT
                    else "[image]"
                    if content.type == PromptMessageContentType.IMAGE
                    else "[file]"
                    for content in prompt_message.content
                ])

        return prompt_messages

    def _organize_prompt_messages(
        self,
        current_thoughts: list[PromptMessage],
        history_prompt_messages: list[PromptMessage],
    ) -> list[PromptMessage]:
        prompt_messages = [
            *history_prompt_messages,
            *current_thoughts,
        ]
        if len(current_thoughts) != 0:
            # clear messages after the first iteration
            prompt_messages = self._clear_user_prompt_image_messages(prompt_messages)
        return prompt_messages
