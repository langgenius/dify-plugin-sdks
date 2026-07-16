from collections import UserList
from unittest.mock import MagicMock

import pytest

from dify_plugin.core import plugin_registration as registration_module
from dify_plugin.core.plugin_registration import PluginRegistration


class AppendTrackingList(UserList):
    def __init__(self) -> None:
        super().__init__()
        self.appended: list[object] = []

    def append(self, item: object) -> None:
        self.appended.append(item)
        super().append(item)


def test_configuration_loading_preserves_append_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = MagicMock()
    configuration.plugins.tools = ["tool.yaml"]
    configuration.plugins.models = []
    configuration.plugins.endpoints = []
    configuration.plugins.agent_strategies = []
    configuration.plugins.datasources = []
    configuration.plugins.triggers = []

    def load_configuration(file_path: str, configuration_type: type) -> object:
        del configuration_type
        if file_path == "manifest.yaml":
            return configuration, {}
        return file_path, {}

    monkeypatch.setattr(
        registration_module,
        "_load_configuration",
        load_configuration,
    )
    registration = object.__new__(PluginRegistration)
    registration.tools_configuration = AppendTrackingList()
    registration.models_configuration = []
    registration.endpoints_configuration = []
    registration.agent_strategies_configuration = []
    registration.datasource_configuration = []
    registration.triggers_configuration = []

    registration._load_plugin_configuration()

    assert registration.tools_configuration.appended == ["tool.yaml"]


def test_configuration_list_is_bound_after_provider_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = MagicMock()
    configuration.plugins.tools = ["tool.yaml"]
    configuration.plugins.models = []
    configuration.plugins.endpoints = []
    configuration.plugins.agent_strategies = []
    configuration.plugins.datasources = []
    configuration.plugins.triggers = []
    registration = object.__new__(PluginRegistration)
    old_list = AppendTrackingList()
    new_list = AppendTrackingList()
    registration.tools_configuration = old_list
    registration.models_configuration = []
    registration.endpoints_configuration = []
    registration.agent_strategies_configuration = []
    registration.datasource_configuration = []
    registration.triggers_configuration = []

    def load_configuration(file_path: str, configuration_type: type) -> object:
        del configuration_type
        if file_path == "manifest.yaml":
            return configuration, {}
        registration.tools_configuration = new_list
        return file_path, {}

    monkeypatch.setattr(
        registration_module,
        "_load_configuration",
        load_configuration,
    )

    registration._load_plugin_configuration()

    assert old_list.appended == []
    assert new_list.appended == ["tool.yaml"]
