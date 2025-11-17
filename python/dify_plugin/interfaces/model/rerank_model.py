from abc import abstractmethod
from collections.abc import Sequence

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.rerank import MultiModalRerankResult, RerankResult
from dify_plugin.entities.model.text_embedding import MultiModalContent
from dify_plugin.interfaces.model.ai_model import AIModel


class RerankModel(AIModel):
    """
    Base Model class for rerank model.
    """

    model_type: ModelType = ModelType.RERANK

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
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
        :param top_n: top n
        :param user: unique user id
        :return: rerank result
        """
        raise NotImplementedError

    def _invoke_multimodal(
        self,
        model: str,
        credentials: dict,
        query: MultiModalContent,
        docs: Sequence[MultiModalContent],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> MultiModalRerankResult:
        """Invoke a multimodal rerank model."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement `_invoke_multimodal`. "
            "Implement this method to support multimodal rerank invocations."
        )

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def invoke(
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
        :param top_n: top n
        :param user: unique user id
        :return: rerank result
        """

        with self.timing_context():
            try:
                return self._invoke(model, credentials, query, docs, score_threshold, top_n, user)
            except Exception as e:
                raise self._transform_invoke_error(e) from e

    def invoke_multimodal(
        self,
        model: str,
        credentials: dict,
        query: MultiModalContent,
        docs: Sequence[MultiModalContent],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> MultiModalRerankResult:
        """Invoke a multimodal rerank model."""

        with self.timing_context():
            try:
                return self._invoke_multimodal(
                    model,
                    credentials,
                    query,
                    docs,
                    score_threshold,
                    top_n,
                    user,
                )
            except NotImplementedError:
                raise
            except Exception as e:
                raise self._transform_invoke_error(e) from e
