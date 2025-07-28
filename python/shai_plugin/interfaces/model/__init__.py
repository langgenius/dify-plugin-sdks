from abc import ABC, abstractmethod

from shai_plugin.entities.model import AIModelEntity, ModelType
from shai_plugin.entities.model.provider import ProviderEntity
from shai_plugin.interfaces.model.ai_model import AIModel


class ModelProvider(ABC):
    provider_schema: ProviderEntity
    model_instance_map: dict[ModelType, AIModel]

    def __init__(
        self,
        provider_schemas: ProviderEntity,
        model_instance_map: dict[ModelType, AIModel],
    ):
        """
        Initialize model provider

        :param provider_schemas: provider schemas
        :param model_instance_map: model instance map
        """
        self.provider_schema = provider_schemas
        self.model_instance_map = model_instance_map

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
        if model_type in self.model_instance_map:
            return self.model_instance_map[model_type]

        raise ValueError(f"Model instance not found for model type: {model_type}")
