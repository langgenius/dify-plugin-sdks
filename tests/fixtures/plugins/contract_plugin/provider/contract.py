from dify_plugin.interfaces.tool import ToolProvider


class ContractProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        if credentials.get("api_key") != "valid":
            msg = "invalid credentials"
            raise ValueError(msg)
