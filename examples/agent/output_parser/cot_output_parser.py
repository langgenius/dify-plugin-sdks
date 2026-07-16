import json
import re
from collections.abc import Generator

from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.interfaces.agent import AgentScratchpadUnit

CODE_BLOCK_DELIMITER_COUNT = 3
TRIM_BOUNDARY_CHARACTERS = frozenset(("\n", " ", ""))


class CotAgentOutputParser:
    @classmethod
    def handle_react_stream_output(
        cls,
        llm_response: Generator[LLMResultChunk, None, None],
        usage_dict: dict,
    ) -> Generator[str | AgentScratchpadUnit.Action, None, None]:
        def parse_action(json_str: str) -> str | AgentScratchpadUnit.Action:
            try:
                action = json.loads(json_str, strict=False)
                action_name = None
                action_input = None

                # cohere always returns a list
                if isinstance(action, list) and len(action) == 1:
                    action = action[0]

                for key, value in action.items():
                    if "input" in key.lower():
                        action_input = value
                    else:
                        action_name = value

                if action_name is not None and action_input is not None:
                    return AgentScratchpadUnit.Action(
                        action_name=action_name,
                        action_input=action_input,
                    )
            except Exception:
                return json_str or ""
            return json_str or ""

        def extra_json_from_code_block(
            code_block: str,
        ) -> Generator[str | AgentScratchpadUnit.Action, None, None]:
            code_blocks = re.findall(r"```(.*?)```", code_block, re.DOTALL)
            if not code_blocks:
                return
            for block in code_blocks:
                json_text = re.sub(
                    r"^[a-zA-Z]+\n",
                    "",
                    block.strip(),
                    flags=re.MULTILINE,
                )
                yield parse_action(json_text)

        code_block_cache = ""
        code_block_delimiter_count = 0
        in_code_block = False
        json_cache = ""
        json_quote_count = 0
        in_json = False
        got_json = False

        action_cache = ""
        action_str = "action:"
        action_idx = 0

        thought_cache = ""
        thought_str = "thought:"
        thought_idx = 0

        last_character = ""

        def track_code_block_delimiter(delta: str) -> list[str]:
            nonlocal code_block_cache, code_block_delimiter_count, last_character

            if delta == "`":
                last_character = delta
                code_block_cache += delta
                code_block_delimiter_count += 1
                return []

            pending_output = []
            if not in_code_block and code_block_delimiter_count > 0:
                last_character = delta
                pending_output.append(code_block_cache)
            elif in_code_block:
                last_character = delta
                code_block_cache += delta

            code_block_cache = "" if not in_code_block else code_block_cache
            code_block_delimiter_count = 0
            return pending_output

        def track_marker(
            delta: str,
            marker: str,
            marker_cache: str,
            marker_index: int,
        ) -> tuple[str, int, bool, bool, list[str]]:
            nonlocal last_character

            if delta.lower() != marker[marker_index]:
                if marker_cache:
                    last_character = delta
                    return "", 0, False, False, [marker_cache]
                return marker_cache, marker_index, False, False, []

            if marker_index == 0 and last_character not in TRIM_BOUNDARY_CHARACTERS:
                return marker_cache, marker_index, False, True, []

            last_character = delta
            marker_cache += delta
            marker_index += 1
            if marker_index == len(marker):
                marker_cache = ""
                marker_index = 0
            return marker_cache, marker_index, True, False, []

        def close_code_block() -> Generator[
            str | AgentScratchpadUnit.Action, None, None
        ]:
            nonlocal \
                code_block_cache, \
                code_block_delimiter_count, \
                in_code_block, \
                last_character

            if code_block_delimiter_count != CODE_BLOCK_DELIMITER_COUNT:
                return

            if in_code_block:
                last_character = "`"
                yield from extra_json_from_code_block(code_block_cache)
                code_block_cache = ""

            in_code_block = not in_code_block
            code_block_delimiter_count = 0

        def track_json(
            delta: str,
        ) -> tuple[bool, list[str | AgentScratchpadUnit.Action]]:
            nonlocal got_json, in_json, json_cache, json_quote_count, last_character

            if delta == "{":
                json_quote_count += 1
                in_json = True
                last_character = delta
                json_cache += delta
            elif delta == "}":
                last_character = delta
                json_cache += delta
                if json_quote_count > 0:
                    json_quote_count -= 1
                    if json_quote_count == 0:
                        in_json = False
                        got_json = True
                        return True, []
            elif in_json:
                last_character = delta
                json_cache += delta

            if not got_json:
                return False, []

            got_json = False
            last_character = delta
            parsed_json = parse_action(json_cache)
            json_cache = ""
            json_quote_count = 0
            in_json = False
            return False, [parsed_json]

        for response in llm_response:
            if response.delta.usage:
                usage_dict["usage"] = response.delta.usage
            response_content = response.delta.message.content
            if not isinstance(response_content, str):
                continue

            # stream
            index = 0
            while index < len(response_content):
                steps = 1
                delta = response_content[index : index + steps]
                yield_delta = False

                yield from track_code_block_delimiter(delta)

                if not in_code_block and not in_json:
                    action_cache, action_idx, consumed, yield_delta, output = (
                        track_marker(delta, action_str, action_cache, action_idx)
                    )
                    yield from output
                    if consumed:
                        index += steps
                        continue

                    (
                        thought_cache,
                        thought_idx,
                        consumed,
                        thought_yield_delta,
                        output,
                    ) = track_marker(delta, thought_str, thought_cache, thought_idx)
                    yield_delta = yield_delta or thought_yield_delta
                    yield from output
                    if consumed:
                        index += steps
                        continue

                    if yield_delta:
                        index += steps
                        last_character = delta
                        yield delta
                        continue

                yield from close_code_block()

                if not in_code_block:
                    # handle single json
                    consumed, output = track_json(delta)
                    yield from output
                    if consumed:
                        index += steps
                        continue

                if not in_code_block and not in_json:
                    last_character = delta
                    yield delta.replace("`", "")

                index += steps

        if code_block_cache:
            yield code_block_cache

        if json_cache:
            yield parse_action(json_cache)
