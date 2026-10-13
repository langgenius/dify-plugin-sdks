from enum import Enum
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from dify_plugin.core.documentation import schema_doc
from dify_plugin.core.documentation.generator import SchemaDocumentationGenerator


class ReferencedModel(BaseModel):
    value: str


class ReferencedEnum(Enum):
    VALUE = "value"


@pytest.fixture(autouse=True)
def isolated_schema_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schema_doc, "__cls_mapping__", {})


def _generate(tmp_path: Path) -> str:
    output = tmp_path / "schemas.md"
    SchemaDocumentationGenerator().generate_docs(str(output))
    return output.read_text(encoding="utf-8")


def _section(document: str, name: str) -> str:
    return document.split(f"## {name}\n\n", 1)[1].split("\n## ", 1)[0]


def test_documentation_generator_handles_generic_type_args() -> None:
    generator = SchemaDocumentationGenerator()

    refs = generator._extract_referenced_types(
        list[ReferencedModel] | dict[str, ReferencedEnum],
    )

    assert refs == {ReferencedModel, ReferencedEnum}
    assert generator._is_container_type(list[ReferencedModel])
    assert generator._get_container_name(list[ReferencedModel]) == "list"


def test_schema_registry_keeps_class_identity_and_metadata() -> None:
    class Settings(BaseModel):
        secret: str

    decorated = schema_doc.docs(
        "Runtime settings", name="Configuration", top=True, ignore_fields=["secret"]
    )(Settings)

    assert decorated is Settings
    entry = schema_doc.get_schema_doc(Settings)
    assert entry is not None
    assert (entry.name, entry.description, entry.top) == (
        "Configuration",
        "Runtime settings",
        True,
    )
    assert entry.ignore_fields == ["secret"]
    assert schema_doc.list_schema_docs() == [entry]
    assert schema_doc.get_schema_doc(ReferencedModel) is None


def test_empty_registry_still_creates_valid_document(tmp_path: Path) -> None:
    document = _generate(tmp_path)

    assert document.startswith("# Dify Plugin SDK Schema Documentation\n")
    assert "## Table of Contents\n" in document
    assert "### Fields" not in document


def test_fields_include_types_descriptions_defaults_and_constraints(
    tmp_path: Path,
) -> None:
    @schema_doc.docs("Connection settings", name="Connection", top=True)
    class Settings(BaseModel):
        host: str = Field(description="服务器地址")
        port: int = Field(default=443, ge=1, le=65535)
        labels: set[str] = Field(default_factory=set)
        aliases: list[str]
        headers: dict[str, str]
        bounds: tuple[int, int]
        enabled: bool = True
        token: str | None = None
        mode: Literal["chat", "completion"] = "chat"

    document = _generate(tmp_path)
    fields = _section(document, "Connection")

    assert "- [Connection](#connection)" in document
    assert "Connection settings" in fields
    assert "| host | str | 服务器地址 |  |" in fields
    assert "| port | int |  | 443 |" in fields
    assert "Ge(ge=1)" in fields
    assert "Le(le=65535)" in fields
    assert "| labels | set[str] |" in fields
    assert "| aliases | list[str] |" in fields
    assert "| headers | dict[str, str] |" in fields
    assert "| bounds | tuple[int, int] |" in fields
    assert "| enabled | bool |  | True |" in fields
    assert "| token | Union[str, NoneType] |  | None |" in fields
    assert "Literal['chat', 'completion']" in fields
    assert "PydanticUndefined" not in document


def test_nested_and_shared_models_document_every_field(tmp_path: Path) -> None:
    @schema_doc.docs("A postal address", name="PostalAddress")
    class Address(BaseModel):
        city: str

    @schema_doc.docs("Customer addresses", top=True)
    class Customer(BaseModel):
        home: Address = Field(description="Home address")
        work: Address = Field(description="Work address")
        previous: list[Address]

    @schema_doc.docs("A delivery")
    class Delivery(BaseModel):
        destination: Address

    document = _generate(tmp_path)
    customer = _section(document, "Customer")
    delivery = _section(document, "Delivery")

    assert "| home | [PostalAddress](#postaladdress) | Home address |" in customer
    assert "| work | [PostalAddress](#postaladdress) | Work address |" in customer
    assert "| previous | list[[PostalAddress](#postaladdress)] |" in customer
    assert "| destination | [PostalAddress](#postaladdress) |" in delivery
    assert document.count("## PostalAddress\n") == 1
    assert "\n- [PostalAddress](#postaladdress)\n" in document
    assert document.index("## Customer\n") < document.index("## PostalAddress\n")


def test_toc_nests_unique_references_and_handles_self_references(
    tmp_path: Path,
) -> None:
    @schema_doc.docs("A tree node")
    class Node(BaseModel):
        children: list["Node"] = Field(default_factory=list)

    @schema_doc.docs("A tree", top=True)
    class Tree(BaseModel):
        root: Node

    document = _generate(tmp_path)

    assert "- [Tree](#tree)\n  - [Node](#node)\n" in document
    assert document.count("[Node](#node)\n") == 1
    assert "| children | list[[Node](#node)] |" in _section(document, "Node")


def test_cyclic_models_generate_finite_document(tmp_path: Path) -> None:
    @schema_doc.docs("One side of a cycle")
    class Left(BaseModel):
        right: "Right | None" = None

    @schema_doc.docs("The other side of a cycle")
    class Right(BaseModel):
        left: Left | None = None

    Left.model_rebuild()
    document = _generate(tmp_path)

    assert document.count("## Left\n") == 1
    assert document.count("## Right\n") == 1
    assert "| right | Union[[Right](#right), NoneType] |" in document
    assert "| left | Union[[Left](#left), NoneType] |" in document


def test_enum_schema_describes_values_and_references(tmp_path: Path) -> None:
    @schema_doc.docs("How the request is processed", name="RequestMode")
    class Mode(Enum):
        CHAT = "chat"
        COMPLETION = "completion"

    @schema_doc.docs("A model request")
    class Request(BaseModel):
        mode: Mode

    document = _generate(tmp_path)
    modes = _section(document, "RequestMode")

    assert "How the request is processed" in modes
    assert "### Values\n" in modes
    assert "- `CHAT`: chat\n" in modes
    assert "- `COMPLETION`: completion\n" in modes
    assert "| mode | [RequestMode](#requestmode) |" in _section(document, "Request")


def test_ignored_fields_and_external_yaml_references(tmp_path: Path) -> None:
    @schema_doc.docs("Provider settings", name="ProviderConfig")
    class Provider(BaseModel):
        name: str

    @schema_doc.docs(
        "A plugin manifest",
        top=True,
        ignore_fields=["secret"],
        outside_reference_fields={"providers": Provider, "primary": Provider},
    )
    class Manifest(BaseModel):
        providers: list[Provider] = Field(description="Provider declarations")
        primary: Provider
        secret: str

    document = _generate(tmp_path)
    manifest = _section(document, "Manifest")

    assert (
        "| providers | list[str] | Provider declarations (Paths to yaml files"
        in manifest
    )
    assert "| primary | str | Paths to yaml files" in manifest
    assert "loaded as [ProviderConfig](#providerconfig)" in manifest
    assert "| secret |" not in manifest
    assert "  - [ProviderConfig](#providerconfig)" in document


def test_unknown_output_directory_preserves_filesystem_error(tmp_path: Path) -> None:
    output = tmp_path / "missing" / "schemas.md"

    with pytest.raises(FileNotFoundError):
        SchemaDocumentationGenerator().generate_docs(str(output))

    assert not output.exists()


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (None, "Any"),
        ("DeferredModel", "DeferredModel"),
        (ReferencedEnum, "[ReferencedEnum](#referencedenum)"),
    ],
)
def test_format_unregistered_or_unresolved_annotation(
    annotation: object, expected: str
) -> None:
    assert SchemaDocumentationGenerator()._format_type_name(annotation) == expected
