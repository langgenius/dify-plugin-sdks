import pytest

from tests.interfaces.model.utils import StubLLM


@pytest.mark.parametrize(
    ("text", "stop", "expected"),
    [
        ("hello.world", [r"\."], "hello.world"),
        ("hello.world", ["."], "hello"),
        ("answer[END]ignored", ["[END]"], "answer"),
        ("answer\\ignored", [r"\\"], "answer\\ignored"),
        ("answer\\ignored", ["\\"], "answer"),
        ("first\nsecond", [r"\n"], "first\nsecond"),
        (r"first\nsecond", [r"\n"], "first"),
        ("first\nsecond", ["\n"], "first"),
        ("answer[ignored", ["["], "answer"),
        ("answer(a|b)*ignored", ["(a|b)*"], "answer"),
        ("first<stop>second<end>", ["<end>", "<stop>"], "first"),
        ("abcdef", ["cd", "bcde"], "a"),
        ("abcdef", ["bcde", "cd"], "a"),
        ("keep all of this", ["<end>"], "keep all of this"),
        ("keep all of this", [], "keep all of this"),
        ("stop at the start", [""], ""),
        ("", ["stop"], ""),
    ],
)
def test_stop_sequences_match_the_earliest_literal_text(
    text: str, stop: list[str], expected: str
) -> None:
    assert StubLLM([]).enforce_stop_tokens(text, stop) == expected
