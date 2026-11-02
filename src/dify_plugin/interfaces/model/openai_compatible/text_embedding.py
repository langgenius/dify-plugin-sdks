import json
import math
import time
from decimal import Decimal
from http import HTTPStatus
from operator import itemgetter

import httpx2

from dify_plugin.core.utils import http
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    AIModelEntity,
    EmbeddingInputType,
    FetchFrom,
    ModelPropertyKey,
    ModelType,
    PriceConfig,
    PriceType,
)
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    TextEmbeddingResult,
)
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
)
from dify_plugin.interfaces.model.openai_compatible.common import _CommonOaiApiCompat
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel


def _validate_embedding_batch(
    data: object, count: int, dimension: int | None
) -> list[list[float]]:
    if not isinstance(data, list) or len(data) != count:
        msg = "Embedding response must contain one vector per input"
        raise ValueError(msg)
    if any(not isinstance(row, dict) for row in data):
        msg = "Embedding response entries must be objects"
        raise ValueError(msg)

    if any("index" in row for row in data):
        indices = [row.get("index") for row in data]
        if any(type(index) is not int for index in indices) or sorted(indices) != list(
            range(count)
        ):
            msg = "Embedding indices must cover every input exactly once"
            raise ValueError(msg)
        data = sorted(data, key=itemgetter("index"))

    vectors = []
    for row in data:
        vector = row.get("embedding")
        if not isinstance(vector, list) or not vector:
            msg = "Embedding vectors must be nonempty arrays"
            raise ValueError(msg)
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension:
            msg = "Embedding vectors must have consistent dimensions across batches"
            raise ValueError(msg)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in vector
        ):
            msg = "Embedding vectors must contain finite numeric values"
            raise ValueError(msg)
        vectors.append(vector)
    return vectors


def _validate_credentials_response(response: httpx2.Response) -> None:
    if response.status_code != HTTPStatus.OK:
        msg = f"Credentials validation failed with status code {response.status_code}"
        raise CredentialsValidateFailedError(msg)

    try:
        json_result = response.json()
    except json.JSONDecodeError as e:
        msg = "Credentials validation failed: JSON decode error"
        raise CredentialsValidateFailedError(msg) from e
    except CredentialsValidateFailedError:
        raise

    if "model" not in json_result:
        msg = "Credentials validation failed: invalid response"
        raise CredentialsValidateFailedError(msg)


class OAICompatEmbeddingModel(_CommonOaiApiCompat, TextEmbeddingModel):
    """
    Model class for an OpenAI API-compatible text embedding model.
    """

    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        """
        Invoke text embedding model

        :param model: model name
        :param credentials: model credentials
        :param texts: texts to embed
        :param user: unique user id
        :param input_type: input type
        :return: embeddings result

        Returns:
            The return value.
        """
        del input_type

        # Prepare headers and payload for the request
        headers = {"Content-Type": "application/json"}

        api_key = credentials.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint_url = self._join_endpoint_url(
            credentials.get("endpoint_url", ""),
            "embeddings",
        )

        extra_model_kwargs = {}
        if user:
            extra_model_kwargs["user"] = user

        extra_model_kwargs["encoding_format"] = "float"

        # get model properties
        context_size = self._get_context_size(model, credentials)
        max_chunks = self._get_max_chunks(model, credentials)

        inputs = []
        indices = []
        used_tokens = 0

        for i, text in enumerate(texts):
            # Here token count is only an approximation based on the GPT2 tokenizer
            # Better token estimation would make chunking more precise.
            num_tokens = self._get_num_tokens_by_gpt2(text)

            if num_tokens >= context_size:
                cutoff = int((len(text) * context_size) // num_tokens)
                # if num tokens is larger than context length, only use the start
                inputs.append(text[0:cutoff])
            else:
                inputs.append(text)
            indices += [i]

        batched_embeddings = []
        dimension = None
        iter_ = range(0, len(inputs), max_chunks)

        for i in iter_:
            # Prepare the payload for the request
            payload = {
                "input": inputs[i : i + max_chunks],
                "model": credentials.get("endpoint_model_name", model),
                **extra_model_kwargs,
            }

            with http.client() as client:
                response = client.post(
                    endpoint_url,
                    headers=http.headers(headers),
                    json=payload,
                    timeout=httpx2.Timeout(300, connect=10, write=10),
                    follow_redirects=True,
                )
            response.raise_for_status()
            response_data = response.json()
            embeddings_batch = _validate_embedding_batch(
                response_data["data"], len(payload["input"]), dimension
            )
            embedding_used_tokens = response_data["usage"]["total_tokens"]

            dimension = len(embeddings_batch[0])
            used_tokens += embedding_used_tokens
            batched_embeddings += embeddings_batch

        # calc usage
        usage = self._calc_response_usage(
            model=model, credentials=credentials, tokens=used_tokens
        )

        return TextEmbeddingResult(
            embeddings=batched_embeddings, usage=usage, model=model
        )

    def get_num_tokens(
        self, model: str, credentials: dict, texts: list[str]
    ) -> list[int]:
        """
        Approximate number of tokens for given messages using GPT2 tokenizer

        :param model: model name
        :param credentials: model credentials
        :param texts: texts to embed
        :return:

        Returns:
            The return value.
        """
        del model
        del credentials
        return [self._get_num_tokens_by_gpt2(text) for text in texts]

    def _request_credentials_validation(
        self,
        model: str,
        credentials: dict,
    ) -> httpx2.Response:
        headers = {"Content-Type": "application/json"}
        if api_key := credentials.get("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint_url = self._join_endpoint_url(
            credentials.get("endpoint_url", ""),
            "embeddings",
        )
        payload = {
            "input": ["ping"],
            "model": credentials.get("endpoint_model_name", model),
        }
        with http.client() as client:
            return client.post(
                endpoint_url,
                headers=http.headers(headers),
                json=payload,
                timeout=httpx2.Timeout(300, connect=10, write=10),
                follow_redirects=True,
            )

    def validate_credentials(self, model: str, credentials: dict) -> None:
        """
        Validate model credentials

        :param model: model name
        :param credentials: model credentials
        :return:

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
        """
        try:
            response = self._request_credentials_validation(
                model,
                credentials,
            )
        except CredentialsValidateFailedError:
            raise
        except Exception as ex:
            raise CredentialsValidateFailedError(str(ex)) from ex

        try:
            _validate_credentials_response(response)
        except CredentialsValidateFailedError:
            raise
        except Exception as ex:
            raise CredentialsValidateFailedError(str(ex)) from ex

    def get_customizable_model_schema(
        self, model: str, credentials: dict
    ) -> AIModelEntity:
        """
        generate custom model entities from credentials
        """
        return AIModelEntity(
            model=model,
            label=I18nObject(en_us=model),
            model_type=ModelType.TEXT_EMBEDDING,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            model_properties={
                ModelPropertyKey.CONTEXT_SIZE: int(
                    credentials.get("context_size", 512)
                ),
                ModelPropertyKey.MAX_CHUNKS: 1,
            },
            parameter_rules=[],
            pricing=PriceConfig(
                input=Decimal(credentials.get("input_price", 0)),
                unit=Decimal(credentials.get("unit", 0)),
                currency=credentials.get("currency", "USD"),
            ),
        )

    def _calc_response_usage(
        self, model: str, credentials: dict, tokens: int
    ) -> EmbeddingUsage:
        """
        Calculate response usage

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
