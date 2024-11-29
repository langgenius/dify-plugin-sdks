from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ...entities import I18nObject


class DefaultParameterName(Enum):
    """
    Enum class for parameter template variable.
    """

    TEMPERATURE = "temperature"
    TOP_P = "top_p"
    PRESENCE_PENALTY = "presence_penalty"
    FREQUENCY_PENALTY = "frequency_penalty"
    MAX_TOKENS = "max_tokens"
    RESPONSE_FORMAT = "response_format"
    JSON_SCHEMA = "json_schema"

    @classmethod
    def value_of(cls, value: Any) -> "DefaultParameterName":
        """
        Get parameter name from value.

        :param value: parameter value
        :return: parameter name
        """
        for name in cls:
            if name.value == value:
                return name
        raise ValueError(f"invalid parameter name {value}")


PARAMETER_RULE_TEMPLATE: dict[DefaultParameterName, dict] = {
    DefaultParameterName.TEMPERATURE: {
        "label": {
            "en_US": "Temperature",
            "zh_Hans": "温度",
        },
        "type": "float",
        "help": {
            "en_US": "Controls randomness. Lower temperature results in less random completions. As the temperature approaches zero, the model will become deterministic and repetitive. Higher temperature results in more random completions.",
            "zh_Hans": "温度控制随机性。较低的温度会导致较少的随机完成。随着温度接近零，模型将变得确定性和重复性。较高的温度会导致更多的随机完成。",
        },
        "required": False,
        "default": 0.0,
        "min": 0.0,
        "max": 1.0,
        "precision": 2,
    },
    DefaultParameterName.TOP_P: {
        "label": {
            "en_US": "Top P",
            "zh_Hans": "Top P",
        },
        "type": "float",
        "help": {
            "en_US": "Controls diversity via nucleus sampling: 0.5 means half of all likelihood-weighted options are considered.",
            "zh_Hans": "通过核心采样控制多样性：0.5表示考虑了一半的所有可能性加权选项。",
        },
        "required": False,
        "default": 1.0,
        "min": 0.0,
        "max": 1.0,
        "precision": 2,
    },
    DefaultParameterName.PRESENCE_PENALTY: {
        "label": {
            "en_US": "Presence Penalty",
            "zh_Hans": "存在惩罚",
        },
        "type": "float",
        "help": {
            "en_US": "Applies a penalty to the log-probability of tokens already in the text.",
            "zh_Hans": "对文本中已有的标记的对数概率施加惩罚。",
        },
        "required": False,
        "default": 0.0,
        "min": 0.0,
        "max": 1.0,
        "precision": 2,
    },
    DefaultParameterName.FREQUENCY_PENALTY: {
        "label": {
            "en_US": "Frequency Penalty",
            "zh_Hans": "频率惩罚",
        },
        "type": "float",
        "help": {
            "en_US": "Applies a penalty to the log-probability of tokens that appear in the text.",
            "zh_Hans": "对文本中出现的标记的对数概率施加惩罚。",
        },
        "required": False,
        "default": 0.0,
        "min": 0.0,
        "max": 1.0,
        "precision": 2,
    },
    DefaultParameterName.MAX_TOKENS: {
        "label": {
            "en_US": "Max Tokens",
            "zh_Hans": "最大标记",
        },
        "type": "int",
        "help": {
            "en_US": "Specifies the upper limit on the length of generated results. If the generated results are truncated, you can increase this parameter.",
            "zh_Hans": "指定生成结果长度的上限。如果生成结果截断，可以调大该参数。",
        },
        "required": False,
        "default": 64,
        "min": 1,
        "max": 2048,
        "precision": 0,
    },
    DefaultParameterName.RESPONSE_FORMAT: {
        "label": {
            "en_US": "Response Format",
            "zh_Hans": "回复格式",
        },
        "type": "string",
        "help": {
            "en_US": "Set a response format, ensure the output from llm is a valid code block as possible, such as JSON, XML, etc.",
            "zh_Hans": "设置一个返回格式，确保llm的输出尽可能是有效的代码块，如JSON、XML等",
        },
        "required": False,
        "options": ["JSON", "XML"],
    },
    DefaultParameterName.JSON_SCHEMA: {
        "label": {
            "en_US": "JSON Schema",
        },
        "type": "text",
        "help": {
            "en_US": "Set a response json schema will ensure LLM to adhere it.",
            "zh_Hans": "设置返回的json schema，llm将按照它返回",
        },
        "required": False,
    },
}


class ModelType(Enum):
    """
    Enum class for model type.
    """

    LLM = "llm"
    TEXT_EMBEDDING = "text-embedding"
    RERANK = "rerank"
    SPEECH2TEXT = "speech2text"
    MODERATION = "moderation"
    TTS = "tts"
    TEXT2IMG = "text2img"


class FetchFrom(Enum):
    """
    Enum class for fetch from.
    """

    PREDEFINED_MODEL = "predefined-model"
    CUSTOMIZABLE_MODEL = "customizable-model"


class ModelFeature(Enum):
    """
    Enum class for llm feature.
    """

    TOOL_CALL = "tool-call"
    MULTI_TOOL_CALL = "multi-tool-call"
    AGENT_THOUGHT = "agent-thought"
    VISION = "vision"
    STREAM_TOOL_CALL = "stream-tool-call"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"


class ParameterType(Enum):
    """
    Enum class for parameter type.
    """

    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOLEAN = "boolean"
    TEXT = "text"


class ModelPropertyKey(Enum):
    """
    Enum class for model property key.
    """

    MODE = "mode"
    CONTEXT_SIZE = "context_size"
    MAX_CHUNKS = "max_chunks"
    FILE_UPLOAD_LIMIT = "file_upload_limit"
    SUPPORTED_FILE_EXTENSIONS = "supported_file_extensions"
    MAX_CHARACTERS_PER_CHUNK = "max_characters_per_chunk"
    DEFAULT_VOICE = "default_voice"
    VOICES = "voices"
    WORD_LIMIT = "word_limit"
    AUDIO_TYPE = "audio_type"
    MAX_WORKERS = "max_workers"


class ProviderModel(BaseModel):
    """
    Model class for provider model.
    """

    model: str
    label: I18nObject
    model_type: ModelType
    features: Optional[list[ModelFeature]] = None
    fetch_from: FetchFrom = Field(default=FetchFrom.PREDEFINED_MODEL)
    model_properties: dict[ModelPropertyKey, Any]
    deprecated: bool = False
    model_config = ConfigDict(protected_namespaces=())

    """
        use model as label
    """

    @model_validator(mode="before")
    def validate_label(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if not data.get("label"):
                data["label"] = I18nObject(en_US=data["model"])

        return data


class ParameterRule(BaseModel):
    """
    Model class for parameter rule.
    """

    name: str
    use_template: Optional[str] = None
    label: I18nObject
    type: ParameterType
    help: Optional[I18nObject] = None
    required: bool = False
    default: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    precision: Optional[int] = None
    options: list[str] = []

    @model_validator(mode="before")
    def validate_label(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if not data.get("label"):
                data["label"] = I18nObject(en_US=data["name"])

            # check if there is a template
            if "use_template" in data:
                try:
                    default_parameter_name = DefaultParameterName.value_of(
                        data["use_template"]
                    )
                    default_parameter_rule = PARAMETER_RULE_TEMPLATE.get(
                        default_parameter_name
                    )
                    if not default_parameter_rule:
                        raise Exception(
                            f"Invalid model parameter rule name {default_parameter_name}"
                        )
                    copy_default_parameter_rule = default_parameter_rule.copy()
                    copy_default_parameter_rule.update(data)
                    data = copy_default_parameter_rule
                except ValueError:
                    pass

        return data


class PriceConfig(BaseModel):
    """
    Model class for pricing info.
    """

    input: Decimal
    output: Optional[Decimal] = None
    unit: Decimal
    currency: str


class AIModelEntity(ProviderModel):
    """
    Model class for AI model.
    """

    parameter_rules: list[ParameterRule] = []
    pricing: Optional[PriceConfig] = None


class ModelUsage(BaseModel):
    pass


class PriceType(Enum):
    """
    Enum class for price type.
    """

    INPUT = "input"
    OUTPUT = "output"


class PriceInfo(BaseModel):
    """
    Model class for price info.
    """

    unit_price: Decimal
    unit: Decimal
    total_amount: Decimal
    currency: str


class BaseModelConfig(BaseModel):
    provider: str
    model: str
    model_type: ModelType

    model_config = ConfigDict(protected_namespaces=())


class EmbeddingInputType(Enum):
    """
    Enum for embedding input type.
    """

    DOCUMENT = "document"
    QUERY = "query"
