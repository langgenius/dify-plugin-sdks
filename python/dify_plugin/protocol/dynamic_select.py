from typing import Protocol

from dify_plugin.entities import ParameterOption


class DynamicSelectProtocol(Protocol):
    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options.

        Classes that implement this protocol should have at least one parameter with type `dynamic-select`.

        At some scenarios, we don't know the available options,
        it could not be defined in the plugin directly.

        But we can fetch the options from the external service such as Slack,
        by providing the access token of the user, we could fetch the channel list of the user.

        That's what this protocol is for.
        """
        ...
