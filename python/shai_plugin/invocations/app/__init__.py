from collections.abc import Mapping

from shai_plugin.core.entities.invocation import InvokeType
from shai_plugin.core.runtime import BackwardsInvocation


class FetchAppInvocation(BackwardsInvocation[dict]):
    def get(
        self,
        app_id: str,
    ) -> Mapping:
        """
        Invoke chat app
        """
        response = self._backwards_invoke(
            InvokeType.FetchApp,
            dict,
            {
                "app_id": app_id,
            },
        )

        for data in response:
            return data

        raise Exception("No response")
