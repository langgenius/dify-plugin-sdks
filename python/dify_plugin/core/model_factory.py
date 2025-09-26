from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ModelProviderConfiguration
from dify_plugin.interfaces.model.ai_model import AIModel


class ModelFactory:
    """
    Model factory

    Given provider configurations and its model list, generate stateless model instances.
    """

    def __init__(self, provider: ModelProviderConfiguration, models: dict[ModelType, type[AIModel]]):
        """
        Initialize model instance factory

        :param provider: model provider configuration
        :param models: model classes
        """
        self.provider = provider
        self.models = models

    def get_instance(self, model_type: ModelType):
        """
        Get model instance

        :param model_type: model type
        :return: model instance
        """
        return self.models[model_type](self.provider.models)

    def get_model_cls(self, model_type: ModelType):
        """
        Get model class

        :param model_type: model type
        :return: model class
        """
        return self.models[model_type]
