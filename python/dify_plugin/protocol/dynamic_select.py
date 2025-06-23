from typing import Protocol

from dify_plugin.entities import ParameterOption


class DynamicSelectProtocol(Protocol):
    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        ...
