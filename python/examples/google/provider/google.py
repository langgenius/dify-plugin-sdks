from typing import Any

from tools.google_search import GoogleSearchTool

from shai_plugin import ToolProvider
from shai_plugin.errors.tool import ToolProviderCredentialValidationError


class GoogleProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            for _ in GoogleSearchTool.from_credentials(credentials).invoke(
                tool_parameters={"query": "test", "result_type": "link"},
            ):
                pass
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
