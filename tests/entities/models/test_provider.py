from dify_plugin.entities.model.provider import FormOption


def test_form_option_uses_value_as_default_label() -> None:
    option = FormOption(value="gpt-4")

    assert option.label.en_US == "gpt-4"
    assert option.label.zh_Hans == "gpt-4"
    assert option.value == "gpt-4"
