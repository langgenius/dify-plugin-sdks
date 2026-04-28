import pathlib
import socket
import sys
from collections.abc import Generator
from typing import ClassVar

import pytest
from xprocess import ProcessStarter, XProcess

from ..consts.mockserver import OPENAI_MOCK_SERVER_PORT

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def openai_mock_server(xprocess: XProcess) -> Generator[str, None, None]:
    class Starter(ProcessStarter):
        pattern = "OpenAI mock server starting"
        args: ClassVar[list[str]] = [sys.executable, "-m", "tests.__mock_server"]
        max_read_lines = 20
        timeout = 30
        terminate_on_interrupt = True
        popen_kwargs: ClassVar[dict[str, str]] = {"cwd": str(PROJECT_ROOT)}

        def startup_check(self) -> bool:
            try:
                with socket.create_connection(
                    ("127.0.0.1", OPENAI_MOCK_SERVER_PORT), timeout=1
                ):
                    return True
            except OSError:
                return False

    xprocess.ensure("openai-mock-server", Starter)
    yield f"http://127.0.0.1:{OPENAI_MOCK_SERVER_PORT}"
    xprocess.getinfo("openai-mock-server").terminate()
