import argparse

from dify_plugin.commands.generate_docs import generate_docs


def main():
    parser = argparse.ArgumentParser(description="Dify Plugin SDK Documentation Generator")
    parser.add_argument("command", choices=["generate-docs"], help="Command to run")
    parser.add_argument(
        "--format",
        choices=["markdown", "json-schema"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: docs.md for markdown, schema.json for json-schema)",
    )
    args = parser.parse_args()

    if args.command == "generate-docs":
        if args.output is None:
            output_file = "schema.json" if args.format == "json-schema" else "docs.md"
        else:
            output_file = args.output

        generate_docs(output_file=output_file, output_format=args.format)


if __name__ == "__main__":
    main()
