from abc import ABC, abstractmethod
from typing import final

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.entities.model import AIModelEntity, ModelType
from dify_plugin.entities.model.provider import ProviderEntity
from dify_plugin.interfaces.model.ai_model import AIModel


class ModelProvider(ABC):
    provider_schema: ProviderEntity
    model_factory: ModelFactory

    @final
    def __init__(
        self,
        provider_schemas: ProviderEntity,
        model_factory: ModelFactory,
    ):
        """
        Initialize model provider

        :param provider_schemas: provider schemas
        :param model_factory: model factory
        """
        self.provider_schema = provider_schemas
        self.model_factory = model_factory

    @abstractmethod
    def validate_provider_credentials(self, credentials: dict) -> None:
        """
        Validate provider credentials
        You can choose any validate_credentials method of model type or implement validate method by yourself,
        such as: get model list api

        if validate failed, raise exception

        :param credentials: provider credentials, credentials form defined in `provider_credential_schema`.
        """
        raise NotImplementedError

    def get_provider_schema(self) -> ProviderEntity:
        """
        Get provider schema

        :return: provider schema
        """
        return self.provider_schema

    def models(self, model_type: ModelType) -> list[AIModelEntity]:
        """
        Get all models for given model type

        :param model_type: model type defined in `ModelType`
        :return: list of models
        """
        provider_schema = self.get_provider_schema()
        if model_type not in provider_schema.supported_model_types:
            return []

        # get model instance of the model type
        model_instance = self.get_model_instance(model_type)

        # get predefined models (predefined_models)
        models = model_instance.predefined_models()

        # return models
        return models

    def get_model_instance(self, model_type: ModelType) -> AIModel:
        """
        Get model instance

        :param model_type: model type defined in `ModelType`
        :return:
        """
        return self.model_factory.get_instance(model_type)
