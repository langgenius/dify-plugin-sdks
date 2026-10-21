from dify_plugin.interfaces.model import ModelProvider


class ContractModelProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: dict) -> None:
        if credentials.get("api_key") != "valid":
            message = "invalid credentials"
            raise ValueError(message)
