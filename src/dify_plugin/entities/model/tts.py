from pydantic import BaseModel, ConfigDict

from dify_plugin.entities.model import BaseModelConfig, ModelType


class TTSModelConfig(BaseModelConfig):
    """
    Model class for tts model config.
    """

    model_type: ModelType = ModelType.TTS
    voice: str

    model_config = ConfigDict(protected_namespaces=())


class TTSResult(BaseModel):
    """
    Model class for tts result.
    """

    result: str
