from collections.abc import Generator
from typing import Literal, overload

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation


class CompletionAppInvocation(BackwardsInvocation[dict]):
    @overload
    def invoke(
        self,
        app_id: str,
        inputs: dict,
        response_mode: Literal["streaming"],
        user: str | None = None,
    ) -> Generator[dict, None, None]: ...

    @overload
    def invoke(
        self,
        app_id: str,
        inputs: dict,
        response_mode: Literal["blocking"],
        user: str | None = None,
    ) -> dict: ...

    def invoke(
        self,
        app_id: str,
        inputs: dict,
        response_mode: Literal["streaming", "blocking"] = "blocking",
        user: str | None = None,
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
                "user": user,
            },
        )

        if response_mode == "streaming":
            return response

        for data in response:
            return data

        msg = "No response from completion"
        raise Exception(msg)
