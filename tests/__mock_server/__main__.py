import sys

from .openai import openai_server_mock


def main() -> None:
    sys.stdout.write("OpenAI mock server starting\n")
    sys.stdout.flush()
    openai_server_mock()


if __name__ == "__main__":
    main()
