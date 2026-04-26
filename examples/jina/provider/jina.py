from dify_plugin import ModelProvider
from dify_plugin.entities.model import ModelType
from dify_plugin.errors.model import CredentialsValidateFailedError


class JinaProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: dict) -> None:
        """
        Validate provider credentials
        if validate failed, raise exception

        :param credentials: provider credentials, credentials form defined in
            `provider_credential_schema`.

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
        """
        try:
            model_instance = self.get_model_instance(ModelType.TEXT_EMBEDDING)

            # Use `jina-embeddings-v2-base-en` model for validate,
            # no matter what model you pass in, text completion model or chat model
            model_instance.validate_credentials(
                model="jina-embeddings-v2-base-en", credentials=credentials
            )
        except CredentialsValidateFailedError:
            raise
        except Exception:
            raise
