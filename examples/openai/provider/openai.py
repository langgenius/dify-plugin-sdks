import logging
from collections.abc import Mapping

from dify_plugin import ModelProvider
from dify_plugin.entities.model import ModelType
from dify_plugin.errors.model import CredentialsValidateFailedError

logger = logging.getLogger(__name__)


class OpenAIProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: Mapping) -> None:
        """
        Validate provider credentials
        if validate failed, raise exception

        :param credentials: provider credentials, credentials form defined in
            `provider_credential_schema`.

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
        """
        try:
            model_instance = self.get_model_instance(ModelType.LLM)

            # Use `gpt-3.5-turbo` model for validate,
            # no matter what model you pass in, text completion model or chat model
            model_instance.validate_credentials(
                model="gpt-3.5-turbo", credentials=credentials
            )
        except CredentialsValidateFailedError:
            raise
        except Exception:
            logger.exception(
                "%s credentials validate failed",
                self.get_provider_schema().provider,
            )
            raise
