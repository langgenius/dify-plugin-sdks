import json
from io import BytesIO


def test_stdio_benchmark_bytes_concat(benchmark):
    data = json.dumps({"test": "test" * 1000}) + "\n"
    data = data.encode("utf-8")

    def run_test():
        buffer = b""
        for _ in range(1000):
            buffer += data

    benchmark(run_test)


def test_stdio_benchmark_bytesio(benchmark):
    data = json.dumps({"test": "test" * 1000}) + "\n"
    data = data.encode("utf-8")

    def run_test():
        buffer = BytesIO()
        for _ in range(1000):
            buffer.write(data)

    benchmark(run_test)
