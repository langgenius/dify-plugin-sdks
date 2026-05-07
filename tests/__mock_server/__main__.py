from .openai import openai_server_mock


def main() -> None:
    print("OpenAI mock server starting", flush=True)
    openai_server_mock()


if __name__ == "__main__":
    main()
