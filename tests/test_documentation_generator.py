from enum import Enum

from pydantic import BaseModel

from dify_plugin.core.documentation.generator import SchemaDocumentationGenerator


class ReferencedModel(BaseModel):
    value: str


class ReferencedEnum(Enum):
    VALUE = "value"


def test_documentation_generator_handles_generic_type_args() -> None:
    generator = SchemaDocumentationGenerator()

    refs = generator._extract_referenced_types(
        list[ReferencedModel] | dict[str, ReferencedEnum],
    )

    assert refs == {ReferencedModel, ReferencedEnum}
    assert generator._is_container_type(list[ReferencedModel])
    assert generator._get_container_name(list[ReferencedModel]) == "list"
