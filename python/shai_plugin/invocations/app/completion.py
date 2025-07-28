from collections.abc import Generator
from typing import Literal, overload

from shai_plugin.core.entities.invocation import InvokeType
from shai_plugin.core.runtime import BackwardsInvocation


class CompletionAppInvocation(BackwardsInvocation[dict]):
    @overload
    def invoke(
        self,
        app_id: str,
        inputs: dict,
        response_mode: Literal["streaming"],
    ) -> Generator[dict, None, None]: ...

    @overload
    def invoke(
        self,
        app_id: str,
        inputs: dict,
        response_mode: Literal["blocking"],
    ) -> dict: ...

    def invoke(
        self,
        app_id: str,
        inputs: dict,
        response_mode: Literal["streaming", "blocking"] = "blocking",
    ) -> Generator[dict, None, None] | dict:
        """
        Invoke completion app
        """
        response = self._backwards_invoke(
            InvokeType.App,
            dict,
            {
                "app_id": app_id,
                "inputs": inputs,
                "response_mode": response_mode,
            },
        )

        if response_mode == "streaming":
            return response

        for data in response:
            return data

        raise Exception("No response from completion")
