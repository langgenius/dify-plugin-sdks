from collections.abc import Callable, Mapping
from typing import Any, Optional

from pydantic import BaseModel


class SchemaDoc:
    def __init__(
        self,
        cls: type[BaseModel],
        description: str,
        name: Optional[str] = None,
        top: bool = False,
        ignore_fields: Optional[list[str]] = None,
        outside_reference_fields: Optional[Mapping[str, type[BaseModel]]] = None,
    ):
        self.cls = cls
        self.description = description
        self.name = name
        self.top = top
        self.ignore_fields = ignore_fields or []
        self.outside_reference_fields = outside_reference_fields or {}


__cls_mapping__: dict[type[BaseModel], SchemaDoc] = {}


def docs(
    description: str,
    name: Optional[str] = None,
    top: bool = False,
    ignore_fields: Optional[list[str]] = None,
    outside_reference_fields: Optional[Mapping[str, type[BaseModel]]] = None,
) -> Callable:
    """
    Decorator to add schema documentation to a class

    Args:
        description: Description of the schema
        name: Optional name override for the schema
        example: Optional example instance
        reference: Optional reference to another schema
        dynamic_fields: Optional dynamic field descriptions
        top: Whether this schema should be placed at the top of the documentation
        ignore_fields: List of field names to ignore in documentation
    """

    def decorator(cls_or_func: Any) -> Any:
        # check if cls_or_func is a class
        if isinstance(cls_or_func, type):
            nonlocal name
            name = name or cls_or_func.__name__

            if cls_or_func not in __cls_mapping__:
                __cls_mapping__[cls_or_func] = SchemaDoc(
                    cls_or_func, description, name, top, ignore_fields, outside_reference_fields
                )

            if not hasattr(cls_or_func, "__schema_docs__"):
                cls_or_func.__schema_docs__ = []
            cls_or_func.__schema_docs__.append(__cls_mapping__[cls_or_func])
            return cls_or_func

    return decorator


def get_schema_doc(cls: type[BaseModel]) -> SchemaDoc | None:
    """
    Get the schema documentation for a class
    """
    return __cls_mapping__.get(cls)


def list_schema_docs() -> list[SchemaDoc]:
    """
    List all schema documentation
    """
    return list(__cls_mapping__.values())
