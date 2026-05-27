import pytest
from pydantic import ValidationError

from dify_plugin.entities import I18nObject


def test_i18n_object_uses_legacy_python_attribute_names() -> None:
    i18n = I18nObject.model_validate({
        "en_US": "English",
        "zh_Hans": "简体中文",
        "pt_BR": "Português",
        "ja_JP": "日本語",
    })

    assert i18n.en_US == "English"
    assert i18n.zh_Hans == "简体中文"
    assert i18n.pt_BR == "Português"
    assert i18n.ja_JP == "日本語"
    assert i18n.model_dump() == {
        "en_US": "English",
        "zh_Hans": "简体中文",
        "pt_BR": "Português",
        "ja_JP": "日本語",
    }


def test_i18n_object_fills_missing_translations_from_english() -> None:
    i18n = I18nObject(en_US="English")

    assert i18n.en_US == "English"
    assert i18n.zh_Hans == "English"
    assert i18n.pt_BR == "English"
    assert i18n.ja_JP == "English"

    assert i18n.to_dict() == {
        "en_US": "English",
        "zh_Hans": "English",
        "pt_BR": "English",
        "ja_JP": "English",
    }


def test_i18n_object_does_not_accept_new_python_attribute_names() -> None:
    with pytest.raises(AttributeError):
        _ = I18nObject(en_US="English").en_us

    with pytest.raises(ValidationError):
        I18nObject(en_us="English")
