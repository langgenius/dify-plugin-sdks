from operator import itemgetter
from pathlib import Path

import pytest

from dify_plugin.core.utils.position_helper import (
    get_position_map,
    sort_by_position_map,
    sort_to_dict_by_position_map,
)


@pytest.mark.parametrize("content", [None, "", "[]", "[unterminated"])
def test_absent_empty_or_invalid_positions_mean_no_order(
    tmp_path: Path, content: str | None
) -> None:
    if content is not None:
        (tmp_path / "_position.yaml").write_text(content, encoding="utf-8")

    assert get_position_map(str(tmp_path)) == {}


def test_position_file_preserves_legacy_indices_after_trimming(tmp_path: Path) -> None:
    (tmp_path / "custom.yaml").write_text(
        '- " beta "\n- null\n- 42\n- ""\n- "  "\n- alpha\n', encoding="utf-8"
    )

    assert get_position_map(str(tmp_path), file_name="custom.yaml") == {
        "beta": 0,
        "": 1,
        "alpha": 2,
    }


def test_sort_preserves_unlisted_order_without_mutating_input() -> None:
    items = [{"name": name} for name in ("unknown-b", "alpha", "beta", "unknown-a")]
    original = items.copy()

    ordered = sort_by_position_map({"beta": 0, "alpha": 1}, items, itemgetter("name"))

    assert [item["name"] for item in ordered] == [
        "beta",
        "alpha",
        "unknown-b",
        "unknown-a",
    ]
    assert items == original
    assert ordered[0] is items[2]


@pytest.mark.parametrize(
    ("positions", "items"), [({}, ["beta", "alpha"]), ({"alpha": 0}, [])]
)
def test_sort_without_positions_or_items_preserves_values(
    positions: dict[str, int], items: list[str]
) -> None:
    assert sort_by_position_map(positions, items, str) == items


def test_ordered_mapping_keeps_names_and_original_objects() -> None:
    items = [{"name": "alpha", "value": 1}, {"name": "beta", "value": 2}]

    ordered = sort_to_dict_by_position_map({"beta": 0}, items, itemgetter("name"))

    assert list(ordered) == ["beta", "alpha"]
    assert ordered["beta"] is items[1]
    assert ordered["alpha"] is items[0]
