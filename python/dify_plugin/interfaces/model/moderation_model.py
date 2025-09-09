from abc import abstractmethod

from pydantic import ConfigDict

from dify_plugin.entities.model import ModelType
from dify_plugin.interfaces.model.ai_model import AIModel


class ModerationModel(AIModel):
    """
    Model class for moderation model.
    """

    model_type: ModelType = ModelType.MODERATION

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(self, model: str, credentials: dict, text: str, user: str | None = None) -> bool:
        """
        Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param text: text to moderate
        :param user: unique user id
        :return: false if text is safe, true otherwise
        """
        raise NotImplementedError

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def invoke(self, model: str, credentials: dict, text: str, user: str | None = None) -> bool:
        """
        Invoke moderation model

        :param model: model name
        :param credentials: model credentials
        :param text: text to moderate
        :param user: unique user id
        :return: false if text is safe, true otherwise
        """
        with self.timing_context():
            try:
                return self._invoke(model, credentials, text, user)
            except Exception as e:
                raise self._transform_invoke_error(e) from e
