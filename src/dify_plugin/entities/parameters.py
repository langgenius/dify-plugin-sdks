from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dify_plugin.core.documentation.schema_doc import docs


@docs(
    description="Common i18n object",
)
class I18nObject(BaseModel):
    """Model class for i18n object."""

    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    zh_hans: str | None = Field(default=None, alias="zh_Hans")
    pt_br: str | None = Field(default=None, alias="pt_BR")
    ja_jp: str | None = Field(default=None, alias="ja_JP")
    en_us: str = Field(alias="en_US")

    @model_validator(mode="after")
    def fill_missing_translations(self) -> "I18nObject":
        if not self.zh_hans:
            self.zh_hans = self.en_us
        if not self.pt_br:
            self.pt_br = self.en_us
        if not self.ja_jp:
            self.ja_jp = self.en_us
        return self

    def to_dict(self) -> dict:
        return {
            "zh_Hans": self.zh_hans,
            "en_US": self.en_us,
            "pt_BR": self.pt_br,
            "ja_JP": self.ja_jp,
        }


@docs(
    description="The option of the parameter",
)
class ParameterOption(BaseModel):
    value: str = Field(..., description="The value of the option")
    label: I18nObject = Field(..., description="The label of the option")
    icon: str | None = Field(
        default=None,
        description="The icon of the option, can be a URL or a base64 encoded string",
    )

    @field_validator("value", mode="before")
    @classmethod
    def transform_id_to_str(cls, value: object) -> str:
        if not isinstance(value, str):
            return str(value)
        return value


@docs(
    description="The auto generate of the parameter",
)
class ParameterAutoGenerate(BaseModel):
    class Type(StrEnum):
        PROMPT_INSTRUCTION = "prompt_instruction"

    type: Type


@docs(
    description="The template of the parameter",
)
class ParameterTemplate(BaseModel):
    enabled: bool = Field(..., description="Whether the parameter is jinja enabled")
