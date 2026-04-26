import time
from json import JSONDecodeError, dumps

from models.text_embedding.jina_tokenizer import JinaTokenizer
from requests import post

from dify_plugin import TextEmbeddingModel
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    AIModelEntity,
    EmbeddingInputType,
    FetchFrom,
    ModelPropertyKey,
    ModelType,
    PriceType,
)
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    TextEmbeddingResult,
)
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
    InvokeServerUnavailableError,
)


class JinaTextEmbeddingModel(TextEmbeddingModel):
    """Model class for Jina text embedding model."""

    api_base: str = "https://api.jina.ai/v1"

    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        """Invoke text embedding model

        :param model: model name
        :param credentials: model credentials
        :param texts: texts to embed
        :param user: unique user id
        :return: embeddings result

        Returns:
            The return value.

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
            InvokeAuthorizationError: If model invocation fails.
            InvokeBadRequestError: If model invocation fails.
            InvokeConnectionError: If model invocation fails.
            InvokeRateLimitError: If model invocation fails.
            InvokeServerUnavailableError: If model invocation fails.
        """
        api_key = credentials["api_key"]
        if not api_key:
            raise CredentialsValidateFailedError("api_key is required")

        base_url = credentials.get("base_url", self.api_base)
        base_url = base_url.removesuffix("/")

        url = base_url + "/embeddings"
        headers = {
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        }

        def transform_jina_input_text(model: str, text: str) -> str | dict[str, str]:
            if model == "jina-clip-v1":
                return {"text": text}
            return text

        data = {
            "model": model,
            "input": [transform_jina_input_text(model, text) for text in texts],
        }

        try:
            response = post(url, headers=headers, data=dumps(data))
        except Exception as e:
            raise InvokeConnectionError(str(e)) from e

        if response.status_code != 200:
            try:
                resp = response.json()
                msg = resp["detail"]
                if response.status_code == 401:
                    raise InvokeAuthorizationError(msg)
                if response.status_code == 429:
                    raise InvokeRateLimitError(msg)
                if response.status_code == 500:
                    raise InvokeServerUnavailableError(msg)
                raise InvokeBadRequestError(msg)
            except JSONDecodeError as e:
                raise InvokeServerUnavailableError(
                    f"Failed to convert response to json: {e} with text: "
                    f"{response.text}",
                ) from e

        try:
            resp = response.json()
            embeddings = resp["data"]
            usage = resp["usage"]
        except Exception as e:
            raise InvokeServerUnavailableError(
                f"Failed to convert response to json: {e} with text: {response.text}",
            ) from e

        usage = self._calc_response_usage(
            model=model,
            credentials=credentials,
            tokens=usage["total_tokens"],
        )

        return TextEmbeddingResult(
            model=model,
            embeddings=[[float(data) for data in x["embedding"]] for x in embeddings],
            usage=usage,
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
    ) -> list[int]:
        """Get number of tokens for given prompt messages

        :param model: model name
        :param credentials: model credentials
        :param texts: texts to embed
        :return:

        Returns:
            The return value.
        """
        # use JinaTokenizer to get num tokens
        return [JinaTokenizer.get_num_tokens(text) for text in texts]

    def validate_credentials(self, model: str, credentials: dict) -> None:
        """Validate model credentials

        :param model: model name
        :param credentials: model credentials
        :return:

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
        """
        try:
            self._invoke(model=model, credentials=credentials, texts=["ping"])
        except Exception as e:
            raise CredentialsValidateFailedError(
                f"Credentials validation failed: {e}",
            ) from e

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {
            InvokeConnectionError: [InvokeConnectionError],
            InvokeServerUnavailableError: [InvokeServerUnavailableError],
            InvokeRateLimitError: [InvokeRateLimitError],
            InvokeAuthorizationError: [InvokeAuthorizationError],
            InvokeBadRequestError: [KeyError, InvokeBadRequestError],
        }

    def _calc_response_usage(
        self,
        model: str,
        credentials: dict,
        tokens: int,
    ) -> EmbeddingUsage:
        """Calculate response usage

        :param model: model name
        :param credentials: model credentials
        :param tokens: input tokens
        :return: usage

        Returns:
            The return value.
        """
        # get input price info
        input_price_info = self.get_price(
            model=model,
            credentials=credentials,
            price_type=PriceType.INPUT,
            tokens=tokens,
        )

        # transform usage
        return EmbeddingUsage(
            tokens=tokens,
            total_tokens=tokens,
            unit_price=input_price_info.unit_price,
            price_unit=input_price_info.unit,
            total_price=input_price_info.total_amount,
            currency=input_price_info.currency,
            latency=time.perf_counter() - self.started_at,
        )

    def get_customizable_model_schema(
        self,
        model: str,
        credentials: dict,
    ) -> AIModelEntity:
        """Generate custom model entities from credentials"""
        return AIModelEntity(
            model=model,
            label=I18nObject(en_US=model),
            model_type=ModelType.TEXT_EMBEDDING,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            model_properties={
                ModelPropertyKey.CONTEXT_SIZE: int(
                    credentials.get("context_size") or 128,
                ),
            },
        )
