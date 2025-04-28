import argparse

from dify_plugin.commands.generate_docs import generate_docs


def main():
    parser = argparse.ArgumentParser(description="Dify Plugin SDK Documentation Generator")
    parser.add_argument("command", choices=["generate-docs"], help="Command to run")
    args = parser.parse_args()

    if args.command == "generate-docs":
        generate_docs()


if __name__ == "__main__":
    main()
