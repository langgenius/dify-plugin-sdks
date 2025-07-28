from pydantic import BaseModel, Field, field_validator

from shai_plugin.core.documentation.schema_doc import docs


@docs(
    description="Common i18n object",
)
class I18nObject(BaseModel):
    """
    Model class for i18n object.
    """

    zh_Hans: str | None = None
    pt_BR: str | None = None
    en_US: str

    def __init__(self, **data):
        super().__init__(**data)
        if not self.zh_Hans:
            self.zh_Hans = self.en_US
        if not self.pt_BR:
            self.pt_BR = self.en_US

    def to_dict(self) -> dict:
        return {"zh_Hans": self.zh_Hans, "en_US": self.en_US, "pt_BR": self.pt_BR}


@docs(
    description="The option of the parameter",
)
class ParameterOption(BaseModel):
    value: str = Field(..., description="The value of the option")
    label: I18nObject = Field(..., description="The label of the option")
    icon: str | None = Field(
        default=None, description="The icon of the option, can be a URL or a base64 encoded string"
    )

    @field_validator("value", mode="before")
    @classmethod
    def transform_id_to_str(cls, value) -> str:
        if not isinstance(value, str):
            return str(value)
        else:
            return value
