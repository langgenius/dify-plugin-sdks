import json
from collections import defaultdict
from enum import Enum
from typing import Any, Union

from pydantic import BaseModel

from dify_plugin.core.documentation.schema_doc import list_schema_docs
from dify_plugin.core.entities import *  # noqa: F403
from dify_plugin.core.entities.plugin import *  # noqa: F403
from dify_plugin.core.entities.plugin.setup import *  # noqa: F403
from dify_plugin.entities import *  # noqa: F403
from dify_plugin.entities.agent import *  # noqa: F403
from dify_plugin.entities.endpoint import *  # noqa: F403
from dify_plugin.entities.model import *  # noqa: F403
from dify_plugin.entities.model.llm import *  # noqa: F403
from dify_plugin.entities.model.moderation import *  # noqa: F403
from dify_plugin.entities.model.provider import *  # noqa: F403
from dify_plugin.entities.model.rerank import *  # noqa: F403
from dify_plugin.entities.model.speech2text import *  # noqa: F403
from dify_plugin.entities.model.text_embedding import *  # noqa: F403
from dify_plugin.entities.model.tts import *  # noqa: F403
from dify_plugin.entities.tool import *  # noqa: F403


class SchemaDocumentationGenerator:
    def __init__(self):
        self._reference_counts: dict[type, int] = {}
        self._reference_graph: dict[type, set[type]] = defaultdict(set)
        self._processed_types: set[type] = set()
        self._field_descriptions: dict[tuple[type, str], str] = {}
        self._schema_descriptions: dict[type, str] = {}
        self._processed_field_types: set[type] = set()
        self._type_to_schema: dict[type, Any] = {}
        self._type_blocks: dict[type, int] = {}
        self._blocks: list[list] = []
        self._types: set[type] = set()

    def _organize_toc(self) -> list[tuple[type, list[Any]]]:
        """Organize types into a hierarchical structure for table of contents.

        The hierarchy is built based on the following rules:
        1. Types marked with top=True are placed at the root level first
        2. Types referenced by multiple other types are placed at the root level
        3. Types not referenced by any other type are placed at the root level
        4. Types referenced by exactly one other type are placed as children of their parent type
        5. This process continues recursively for each child type

        This ensures that:
        - Important types (marked with top=True) are easily accessible
        - Types that are part of multiple other types are at root for easy access
        - Types that belong to a single parent are properly nested
        - The hierarchy reflects the actual reference relationships in the code
        - Deep reference chains are properly represented (A -> B -> C shown as nested structure)

        Returns:
            List[Tuple[Type, List[Any]]]: A list of tuples, where each tuple contains:
                - A parent type
                - A list of its child nodes, each being a tuple of (Type, List[Any])
        """
        # Build a reverse reference map: type -> set of types that reference it
        referenced_by = {t: set() for t in self._types}
        for t, refs in self._reference_graph.items():
            for ref in refs:
                if ref in referenced_by:
                    referenced_by[ref].add(t)

        def build_subtree(type_: type, processed: set[type]) -> tuple[type, list[Any]]:
            """Recursively build a subtree for a type and its references.

            Args:
                type_: The type to build a subtree for
                processed: Set of already processed types to avoid cycles

            Returns:
                Tuple[Type, List[Any]]: The type and its nested children
            """
            if type_ in processed:
                return type_, []

            processed.add(type_)
            children = []

            # Find all types that are only referenced by this type
            for ref_type in self._reference_graph.get(type_, set()):
                # If this is the only reference to ref_type
                refs = referenced_by.get(ref_type, set())
                if len(refs) == 1 and next(iter(refs)) == type_:
                    subtree = build_subtree(ref_type, processed)
                    children.append(subtree)

            return type_, children

        # Start building the hierarchy
        hierarchy = []
        processed = set()

        # Phase 1: Add types marked with top=True at the root level
        for t in self._types:
            if t not in processed and hasattr(t, "__schema_docs__") and any(doc.top for doc in t.__schema_docs__):
                subtree = build_subtree(t, processed)
                hierarchy.append(subtree)

        # Phase 2: Add types that are not referenced by any other type
        # or are referenced by multiple types
        remaining = [t for t in self._types if len(referenced_by[t]) != 1]
        for t in remaining:
            if t not in processed:
                subtree = build_subtree(t, processed)
                hierarchy.append(subtree)

        # Phase 3: Add any remaining types that weren't processed
        for t in self._types:
            if t not in processed:
                subtree = build_subtree(t, processed)
                hierarchy.append(subtree)

        return hierarchy

    def generate_docs(self, output_file: str):
        with open(output_file, "w") as f:
            # Write header
            f.write("# Dify Plugin SDK Schema Documentation\n\n")

            schemas = list_schema_docs()

            # Build type to schema mapping
            for schema in schemas:
                self._type_to_schema[schema.cls] = schema
                self._types.add(schema.cls)

            # Pre-process schemas to collect field descriptions
            self._preprocess_schemas(schemas)

            # Count references and build reference graph
            self._build_reference_graph(schemas)

            # Create blocks
            self._create_blocks()

            # Generate table of contents
            f.write("## Table of Contents\n\n")
            hierarchy = self._organize_toc()

            def write_toc_item(node: tuple[type, list[Any]], indent: int = 0):
                type_, children = node
                schema = self._type_to_schema[type_]
                name = schema.name or type_.__name__
                f.write(f"{' ' * (indent * 2)}- [{name}](#{name.lower()})\n")
                for child in children:
                    write_toc_item(child, indent + 1)

            for node in hierarchy:
                write_toc_item(node)
            f.write("\n")

            # Generate documentation for each block
            for block in self._blocks:
                for type_ in block:
                    self._write_schema_doc(f, type_)

    def _preprocess_schemas(self, schemas: list) -> None:
        """Pre-process schemas to collect field descriptions and merge duplicates."""
        # First pass: collect all field descriptions
        for schema in schemas:
            cls = schema.cls
            if not issubclass(cls, BaseModel):
                continue

            # Store schema description
            if cls not in self._schema_descriptions or len(schema.description) > len(self._schema_descriptions[cls]):
                self._schema_descriptions[cls] = schema.description

            # Store field descriptions
            outside_reference_fields = getattr(schema, "outside_reference_fields", {}) or {}
            for field_name, field_info in cls.model_fields.items():
                field_type = field_info.annotation
                if field_type is None:
                    continue

                # For BaseModel types that are not outside references, we'll document them separately
                if (
                    isinstance(field_type, type)
                    and issubclass(field_type, BaseModel)
                    and field_name not in outside_reference_fields
                ):
                    continue

                key = (cls, field_name)
                description = field_info.description or ""

                # Handle dynamic fields
                if hasattr(schema, "dynamic_fields") and schema.dynamic_fields and field_name in schema.dynamic_fields:
                    description = schema.dynamic_fields[field_name]

                # For outside reference fields, append reference information to description
                if field_name in outside_reference_fields:
                    referenced_type = outside_reference_fields[field_name]
                    referenced_schema = self._type_to_schema.get(referenced_type)
                    schema_name = referenced_schema.name if referenced_schema else referenced_type.__name__
                    if description:
                        description = f"{description} "
                        f"(Paths to yaml files that will be loaded as [{schema_name}](#{schema_name.lower()}))"
                    else:
                        description = (
                            f"Paths to yaml files that will be loaded as [{schema_name}](#{schema_name.lower()})"
                        )

                # Store the most detailed description
                if key not in self._field_descriptions or len(description) > len(self._field_descriptions[key]):
                    self._field_descriptions[key] = description

    def _extract_referenced_types(self, field_type):
        """Recursively extract all referenced BaseModel and Enum types from a field type."""
        referenced = set()
        if field_type is None:
            return referenced

        # Handle direct type references (BaseModel and Enum)
        if isinstance(field_type, type):
            if issubclass(field_type, (BaseModel, Enum)):
                referenced.add(field_type)
        # Handle generic types (List, Dict, Union, etc)
        elif (hasattr(field_type, "__origin__") and field_type.__origin__ == Union) or hasattr(field_type, "__args__"):
            # Handle Union types
            for arg in field_type.__args__:
                referenced.update(self._extract_referenced_types(arg))

        return referenced

    def _build_reference_graph(self, schemas: list) -> None:
        """Build a graph of references between types (recursively for all nested types)."""
        for schema in schemas:
            cls = schema.cls
            if not issubclass(cls, BaseModel):
                continue

            # Count references in fields
            for field_name, field_info in cls.model_fields.items():
                field_type = field_info.annotation
                if field_type is None:
                    continue

                # Handle outside reference fields
                outside_reference_fields = getattr(schema, "outside_reference_fields", {}) or {}
                if field_name in outside_reference_fields:
                    referenced_type = outside_reference_fields[field_name]
                    # Add the reference to the graph
                    self._reference_graph[cls].add(referenced_type)
                    self._reference_counts[referenced_type] = self._reference_counts.get(referenced_type, 0) + 1
                    continue

                for ref_type in self._extract_referenced_types(field_type):
                    if ref_type != cls:  # Avoid self-references
                        self._reference_graph[cls].add(ref_type)
                        self._reference_counts[ref_type] = self._reference_counts.get(ref_type, 0) + 1

    def _create_blocks(self) -> None:
        """Create documentation blocks for all types"""
        # First pass: assign each type to a block index
        for type_ in self._types:
            if type_ not in self._type_blocks:
                # If type has top=True, assign it to block 0
                if hasattr(type_, "__schema_docs__") and any(doc.top for doc in type_.__schema_docs__):
                    self._type_blocks[type_] = 0
                else:
                    # Assign to a new block, starting from 1
                    self._type_blocks[type_] = len(self._type_blocks) + 1

        # Second pass: create actual blocks
        # Initialize blocks list with enough empty lists
        max_block_index = max(self._type_blocks.values()) if self._type_blocks else 0
        self._blocks = [[] for _ in range(max_block_index + 1)]

        for type_, block_index in self._type_blocks.items():
            self._blocks[block_index].append(type_)

        # Sort blocks to ensure top types are first
        # Only move block 0 to the front if it contains top types
        if (
            self._blocks
            and self._blocks[0]
            and any(
                hasattr(t, "__schema_docs__") and any(doc.top for doc in t.__schema_docs__) for t in self._blocks[0]
            )
        ):
            top_block = self._blocks[0]
            self._blocks.sort(key=lambda block: 0 if block is top_block else 1)

    def _is_container_type(self, field_type: Any, container_types=(list, set)) -> bool:
        """Check if a field type is a container type (list, set, etc)."""
        try:
            return (
                hasattr(field_type, "__origin__")
                and isinstance(getattr(field_type, "__origin__", None), type)
                and getattr(field_type, "__origin__", None) in container_types
            )
        except Exception:
            return False

    def _get_container_name(self, field_type: Any) -> str:
        """Get the name of a container type."""
        try:
            origin = getattr(field_type, "__origin__", None)
            return origin.__name__ if origin else str(field_type)
        except Exception:
            return str(field_type)

    def _write_schema_doc(self, f, type_) -> None:
        """Write documentation for a single schema."""
        schema = self._type_to_schema[type_]
        name = schema.name or type_.__name__

        f.write(f"## {name}\n\n")

        # Write description
        description = self._schema_descriptions.get(type_, "")
        f.write(f"{description}\n\n")

        if issubclass(type_, BaseModel):
            f.write("### Fields\n\n")
            f.write("| Name | Type | Description | Default | Extra |\n")
            f.write("|------|------|-------------|---------|---------|\n")

            # Track processed fields to avoid duplicates
            processed_fields = set()
            ignore_fields = set(getattr(schema, "ignore_fields", []) or [])
            outside_reference_fields = getattr(schema, "outside_reference_fields", {}) or {}

            for field_name, field_info in type_.model_fields.items():
                if field_name in ignore_fields:
                    continue
                field_type = field_info.annotation
                if field_type is None:
                    continue

                # Skip if we've already processed this field type
                if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                    if field_type in self._processed_field_types:
                        continue
                    self._processed_field_types.add(field_type)

                # Skip if we've already processed this field
                field_key = (field_type, field_name)
                if field_key in processed_fields:
                    continue
                processed_fields.add(field_key)

                # Get the most detailed description
                description = self._field_descriptions.get((type_, field_name), field_info.description or "")

                # Format type name
                type_name = self._format_type_name(field_type)

                # Handle outside reference fields
                if field_name in outside_reference_fields:
                    if self._is_container_type(field_type):
                        type_name = f"{self._get_container_name(field_type)}[str]"
                    else:
                        type_name = "str"

                # Get field metadata
                default = field_info.default
                # User-friendly default value
                if str(default) == "PydanticUndefined":
                    default = ""

                # Get pattern if exists (robust)
                extra = ""
                if hasattr(field_info, "metadata"):
                    for value in field_info.metadata:
                        extra += f"{value} "

                f.write(f"| {field_name} | {type_name} | {description} | {default} | {extra} |\n")

            f.write("\n")

        elif issubclass(type_, Enum):
            f.write("### Values\n\n")
            for member in type_:
                f.write(f"- `{member.name}`: {member.value}\n")
            f.write("\n")

    def _format_type_name(self, field_type: Any) -> str:
        """Format the type name for display, handling complex types and references.

        For BaseModel and Enum types, use their schema name if available.
        For container types (list, dict, etc), recursively format their type arguments.
        """
        if field_type is None:
            return "Any"

        if isinstance(field_type, type):
            if issubclass(field_type, (BaseModel, Enum)):
                # Use schema name if available
                schema = self._type_to_schema.get(field_type)
                name = schema.name if schema else field_type.__name__
                return f"[{name}](#{name.lower()})"
            return field_type.__name__

        if hasattr(field_type, "__origin__") and hasattr(field_type, "__args__"):
            origin = field_type.__origin__
            if origin in (list, set):
                inner_type = self._format_type_name(field_type.__args__[0])
                return f"{origin.__name__}[{inner_type}]"
            elif origin is dict:
                key_type = self._format_type_name(field_type.__args__[0])
                value_type = self._format_type_name(field_type.__args__[1])
                return f"dict[{key_type}, {value_type}]"
            elif origin is tuple:
                types = [self._format_type_name(arg) for arg in field_type.__args__]
                return f"tuple[{', '.join(types)}]"
            elif origin is Union:
                types = [self._format_type_name(arg) for arg in field_type.__args__]
                return f"Union[{', '.join(types)}]"

        return str(field_type)

    def generate_json_schema(self, output_file: str):
        """Generate JSON Schema format documentation."""
        schemas = list_schema_docs()

        # Build type to schema mapping
        for schema in schemas:
            self._type_to_schema[schema.cls] = schema
            self._types.add(schema.cls)

        json_schemas = {}

        for schema in schemas:
            cls = schema.cls
            # Use the resolved name from schema
            name = schema.name or cls.__name__

            if issubclass(cls, BaseModel):
                json_schema = self._convert_basemodel_to_json_schema(cls, schema)
                json_schemas[name] = json_schema
            elif issubclass(cls, Enum):
                json_schema = self._convert_enum_to_json_schema(cls, schema)
                json_schemas[name] = json_schema

        output = {"$schema": "http://json-schema.org/draft-07/schema#", "definitions": json_schemas}

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    def _convert_basemodel_to_json_schema(self, cls: type[BaseModel], schema_doc) -> dict:
        """Convert a Pydantic BaseModel to JSON Schema."""
        properties = {}
        required = []

        ignore_fields = set(getattr(schema_doc, "ignore_fields", []) or [])
        outside_reference_fields = getattr(schema_doc, "outside_reference_fields", {}) or {}

        for field_name, field_info in cls.model_fields.items():
            if field_name in ignore_fields:
                continue

            field_type = field_info.annotation
            if field_type is None:
                continue

            description = field_info.description or ""

            # Handle dynamic fields
            if (
                hasattr(schema_doc, "dynamic_fields")
                and schema_doc.dynamic_fields
                and field_name in schema_doc.dynamic_fields
            ):
                description = schema_doc.dynamic_fields[field_name]

            # Handle outside reference fields
            if field_name in outside_reference_fields:
                referenced_type = outside_reference_fields[field_name]
                referenced_schema = self._type_to_schema.get(referenced_type)
                schema_name = referenced_schema.name if referenced_schema else referenced_type.__name__

                if self._is_container_type(field_type):
                    field_schema = {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"{description} (Paths to yaml files that will be loaded as {schema_name})",
                    }
                else:
                    field_schema = {
                        "type": "string",
                        "description": f"{description} (Path to yaml file that will be loaded as {schema_name})",
                    }
            else:
                field_schema = self._get_json_schema_type(field_type)
                if description:
                    field_schema["description"] = description

            # Handle default values
            if field_info.default is not None and str(field_info.default) != "PydanticUndefined":
                try:
                    # Try to serialize the default value to ensure it's JSON-serializable
                    json.dumps(field_info.default)
                    field_schema["default"] = field_info.default
                except (TypeError, ValueError):
                    # If it's not JSON-serializable, convert to string
                    if isinstance(field_info.default, Enum):
                        field_schema["default"] = field_info.default.value
                    else:
                        field_schema["default"] = str(field_info.default)

            # Handle metadata/constraints
            if hasattr(field_info, "metadata"):
                for metadata in field_info.metadata:
                    # Handle common constraints
                    if hasattr(metadata, "pattern"):
                        field_schema["pattern"] = metadata.pattern
                    if hasattr(metadata, "min_length"):
                        field_schema["minLength"] = metadata.min_length
                    if hasattr(metadata, "max_length"):
                        field_schema["maxLength"] = metadata.max_length
                    if hasattr(metadata, "ge"):
                        field_schema["minimum"] = metadata.ge
                    if hasattr(metadata, "le"):
                        field_schema["maximum"] = metadata.le

            properties[field_name] = field_schema

            # Check if field is required
            if field_info.is_required():
                required.append(field_name)

        result = {
            "type": "object",
            "properties": properties,
        }

        if required:
            result["required"] = required

        description = self._schema_descriptions.get(cls, schema_doc.description)
        if description:
            result["description"] = description

        return result

    def _convert_enum_to_json_schema(self, cls: type[Enum], schema_doc) -> dict:
        """Convert an Enum to JSON Schema."""
        enum_values = [member.value for member in cls]

        # Determine the type of enum values
        if enum_values:
            first_value = enum_values[0]
            if isinstance(first_value, str):
                value_type = "string"
            elif isinstance(first_value, int):
                value_type = "integer"
            elif isinstance(first_value, float):
                value_type = "number"
            elif isinstance(first_value, bool):
                value_type = "boolean"
            else:
                value_type = "string"
        else:
            value_type = "string"

        result = {"type": value_type, "enum": enum_values}

        description = self._schema_descriptions.get(cls, schema_doc.description)
        if description:
            result["description"] = description

        return result

    def _get_json_schema_type(self, field_type: Any) -> dict:
        """Convert a Python type to JSON Schema type definition."""
        if field_type is None:
            return {"type": "null"}

        # Handle primitive types
        if field_type is str:
            return {"type": "string"}
        if field_type is int:
            return {"type": "integer"}
        if field_type is float:
            return {"type": "number"}
        if field_type is bool:
            return {"type": "boolean"}

        # Handle type references
        if isinstance(field_type, type):
            if issubclass(field_type, BaseModel) or issubclass(field_type, Enum):
                schema = self._type_to_schema.get(field_type)
                # Use the resolved name from schema
                name = (schema.name if schema else None) or field_type.__name__
                return {"$ref": f"#/definitions/{name}"}
            elif field_type is dict:
                return {"type": "object"}
            elif field_type is list:
                return {"type": "array"}

        # Handle generic types
        if hasattr(field_type, "__origin__") and hasattr(field_type, "__args__"):
            origin = field_type.__origin__
            if origin in (list, set):
                item_schema = self._get_json_schema_type(field_type.__args__[0])
                return {"type": "array", "items": item_schema}
            elif origin is dict:
                key_type = field_type.__args__[0]
                value_type = field_type.__args__[1]
                key_schema = self._get_json_schema_type(key_type)
                value_schema = self._get_json_schema_type(value_type)

                return {"type": "object", "propertyNames": key_schema, "additionalProperties": value_schema}
            elif origin is tuple:
                items = [self._get_json_schema_type(arg) for arg in field_type.__args__]
                return {"type": "array", "items": items, "minItems": len(items), "maxItems": len(items)}
            elif origin is Union:
                args = field_type.__args__
                if type(None) in args:
                    non_none_types = [arg for arg in args if arg is not type(None)]
                    if len(non_none_types) == 1:
                        schema = self._get_json_schema_type(non_none_types[0])
                        if "type" in schema and isinstance(schema["type"], str):
                            schema["type"] = [schema["type"], "null"]
                        else:
                            return {"anyOf": [schema, {"type": "null"}]}
                        return schema

                schemas = [self._get_json_schema_type(arg) for arg in args]
                return {"anyOf": schemas}

        return {}
