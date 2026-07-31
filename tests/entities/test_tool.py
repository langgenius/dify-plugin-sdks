import pytest

from dify_plugin.entities.tool import ToolParameter


def test_tool_parameter_supports_multiple_select() -> None:
    data = {
        "name": "formats",
        "label": {"en_US": "Formats"},
        "human_description": {"en_US": "Formats to include"},
        "type": "select",
        "form": "form",
        "multiple": True,
        "default": ["markdown", "links"],
    }
    parameter = ToolParameter.model_validate(data)

    assert parameter.model_dump(include={"multiple", "default"}) == {
        "multiple": True,
        "default": ["markdown", "links"],
    }
    boolean_parameter = ToolParameter.model_validate(
        data | {"type": "boolean", "multiple": False, "default": True}
    )
    assert boolean_parameter.default is True


@pytest.mark.parametrize(
    "values",
    [
        {"type": "string", "multiple": True, "default": ["markdown"]},
        {"type": "select", "multiple": True, "default": "markdown"},
        {"type": "select", "multiple": False, "default": ["markdown"]},
    ],
)
def test_tool_parameter_rejects_invalid_multiple_select(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="multiple"):
        ToolParameter.model_validate({
            "name": "formats",
            "label": {"en_US": "Formats"},
            "human_description": {"en_US": "Formats to include"},
            "form": "form",
            **values,
        })


def test_tool_parameter_preserves_show_on_conditions() -> None:
    base = {
        "name": "format",
        "label": {"en_US": "Format"},
        "human_description": {"en_US": "Output format"},
        "type": "select",
        "form": "form",
    }
    conditions = [{"variable": "mode", "value": "advanced"}]
    parameter = ToolParameter.model_validate(
        base
        | {
            "show_on": conditions,
            "options": [
                {
                    "value": "json",
                    "label": {"en_US": "JSON"},
                    "show_on": conditions,
                }
            ],
        }
    )

    assert [condition.model_dump() for condition in parameter.show_on] == conditions
    assert parameter.options
    assert [
        condition.model_dump() for condition in parameter.options[0].show_on
    ] == conditions
    assert ToolParameter.model_validate(parameter.model_dump()) == parameter

    defaulted = ToolParameter.model_validate(
        base | {"options": [{"value": "text", "label": {"en_US": "Text"}}]}
    )
    assert defaulted.show_on == []
    assert defaulted.options
    assert defaulted.options[0].show_on == []
