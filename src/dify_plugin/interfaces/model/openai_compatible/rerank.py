import math
from json import dumps

from requests import HTTPError, post
from yarl import URL

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import AIModelEntity, FetchFrom, ModelType
from dify_plugin.entities.model.rerank import RerankDocument, RerankResult
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeError,
    InvokeServerUnavailableError,
)
from dify_plugin.interfaces.model.rerank_model import RerankModel


class OAICompatRerankModel(RerankModel):
    """Invoke Jina rerank APIs, normalizing unbounded scores from llama.cpp."""

    def _invoke(
        self,
        model: str,
        credentials: dict,
        query: str,
        docs: list[str],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> RerankResult:
        """
        Invoke rerank model

        :param model: model name
        :param credentials: model credentials
        :param query: search query
        :param docs: docs for reranking
        :param score_threshold: score threshold
        :param top_n: top n documents to return
        :param user: unique user id
        :return: rerank result

        Returns:
            The return value.

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
            InvokeServerUnavailableError: If model invocation fails.
            ValueError: If the response contains invalid document indices or scores.
        """
        del user
        if len(docs) == 0:
            return RerankResult(model=model, docs=[])

        server_url = credentials["endpoint_url"]
        model_name = model

        if not server_url:
            msg = "server_url is required"
            raise CredentialsValidateFailedError(msg)
        if not model_name:
            msg = "model_name is required"
            raise CredentialsValidateFailedError(msg)

        url = server_url
        headers = {"Content-Type": "application/json"}
        if api_key := credentials.get("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"

        # Open question: truncate docs before llama.cpp-compatible requests?

        data = {
            "model": credentials.get("endpoint_model_name", model),
            "query": query,
            "documents": docs,
            "top_n": top_n,
            "return_documents": True,
        }

        try:
            response = post(
                str(URL(url) / "rerank"), headers=headers, data=dumps(data), timeout=60
            )
            response.raise_for_status()
        except HTTPError as e:
            raise InvokeServerUnavailableError(str(e)) from e

        results = response.json()
        rerank_documents = []
        scores = [result["relevance_score"] for result in results["results"]]
        if any(
            isinstance(score, bool)
            or not isinstance(score, int | float)
            or not math.isfinite(score)
            for score in scores
        ):
            msg = "Rerank scores must be finite numbers."
            raise ValueError(msg)
        min_score = min(scores, default=0.0)
        max_score = max(scores, default=0.0)
        normalize_scores = min_score < 0 or max_score > 1
        score_range = max_score - min_score if max_score != min_score else 1.0
        if not math.isfinite(score_range):
            msg = "Rerank score range must be finite."
            raise ValueError(msg)

        for result in results["results"]:
            index = result["index"]
            if type(index) is not int or not 0 <= index < len(docs):
                msg = "Rerank response contains an invalid document index."
                raise ValueError(msg)
            text = docs[index]
            document = result.get("document", {})
            if document:
                if isinstance(document, dict):
                    text = document.get("text", docs[index])
                elif isinstance(document, str):
                    text = document

            normalized_score = result["relevance_score"]
            if normalize_scores:
                normalized_score = (normalized_score - min_score) / score_range
            rerank_document = RerankDocument(
                index=index,
                text=text,
                score=normalized_score,
            )
            if score_threshold is None or normalized_score >= score_threshold:
                rerank_documents.append(rerank_document)

        rerank_documents.sort(key=lambda doc: doc.score, reverse=True)
        return RerankResult(model=model, docs=rerank_documents)

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
            self._invoke(
                model=model,
                credentials=credentials,
                query="What is the capital of the United States?",
                docs=[
                    (
                        "Carson City is the capital city of the American state "
                        "of Nevada. At the 2010 United States Census, Carson City "
                        "had a population of 55,274."
                    ),
                    (
                        "The Commonwealth of the Northern Mariana Islands is a "
                        "group of islands in the Pacific Ocean that are a "
                        "political division controlled by the United States. "
                        "Its capital is Saipan."
                    ),
                ],
                score_threshold=0.8,
            )
        except Exception as ex:
            raise CredentialsValidateFailedError(str(ex)) from ex

    def get_customizable_model_schema(
        self, model: str, credentials: dict
    ) -> AIModelEntity:
        """
        generate custom model entities from credentials
        """
        del credentials
        return AIModelEntity(
            model=model,
            label=I18nObject(en_us=model),
            model_type=ModelType.RERANK,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            model_properties={},
        )

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error
        """
        return {}
