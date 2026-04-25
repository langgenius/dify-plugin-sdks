from dify_plugin.core.documentation.generator import SchemaDocumentationGenerator


def generate_docs():
    SchemaDocumentationGenerator().generate_docs("docs.md")
