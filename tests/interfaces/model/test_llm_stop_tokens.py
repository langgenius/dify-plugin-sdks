import pytest

from tests.interfaces.model.utils import StubLLM


@pytest.mark.parametrize(
    ("text", "stop", "expected"),
    [
        ("hello.world", ["."], "hello"),
        ("answer[END]ignored", ["[END]"], "answer"),
        ("answer\\ignored", ["\\"], "answer"),
        ("first<stop>second<end>", ["<end>", "<stop>"], "first"),
        ("keep all of this", ["<end>"], "keep all of this"),
        ("keep all of this", [], "keep all of this"),
    ],
)
def test_stop_sequences_match_literal_text_at_the_first_occurrence(
    text: str, stop: list[str], expected: str
) -> None:
    assert StubLLM([]).enforce_stop_tokens(text, stop) == expected
