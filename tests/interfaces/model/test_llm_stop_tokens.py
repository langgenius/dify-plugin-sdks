import pytest

from tests.interfaces.model.utils import StubLLM


@pytest.mark.parametrize(
    ("text", "stop", "expected"),
    [
        ("hello.world", [r"\."], "hello"),
        ("hello.world", ["."], ""),
        ("answer[END]ignored", ["[END]"], "answer["),
        ("answer\\ignored", [r"\\"], "answer"),
        ("first\nsecond", [r"\n"], "first"),
        ("first<stop>second<end>", ["<end>", "<stop>"], "first"),
        ("keep all of this", ["<end>"], "keep all of this"),
        ("keep all of this", [], ""),
    ],
)
def test_stop_sequences_preserve_regex_matching(
    text: str, stop: list[str], expected: str
) -> None:
    assert StubLLM([]).enforce_stop_tokens(text, stop) == expected
