from dify_plugin.core.documentation.generator import SchemaDocumentationGenerator


def generate_docs(output_file: str = "docs.md", output_format: str = "markdown"):
    generator = SchemaDocumentationGenerator()

    if output_format == "json-schema":
        generator.generate_json_schema(output_file)
    else:
        generator.generate_docs(output_file)
