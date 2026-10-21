import json
import os
import select
import subprocess  # ruff:ignore[suspicious-subprocess-import]
import time
from pathlib import Path
from typing import Any


class StdioPlugin:
    def __init__(self, process: subprocess.Popen[bytes], stderr_path: Path) -> None:
        self.process = process
        self.stderr_path = stderr_path
        self.stdout_path = stderr_path.with_suffix(".stdout")
        self.stdout_path.touch()
        self.manifest: dict[str, Any] = {}
        self.pending = b""

    def read_message(self, deadline: float | None = None) -> dict[str, Any]:
        assert self.process.stdout is not None
        if deadline is None:
            deadline = time.monotonic() + 10
        while True:
            if b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                if line.strip():
                    return json.loads(line)
                continue
            remaining = deadline - time.monotonic()
            if (
                remaining <= 0
                or not select.select([self.process.stdout], [], [], remaining)[0]
            ):
                msg = (
                    f"Plugin response timed out. stdout: {self.stdout_path}; stderr:\n"
                    + self.stderr_path.read_text()
                )
                raise AssertionError(msg)
            data = os.read(self.process.stdout.fileno(), 65536)
            if not data:
                msg = f"Plugin stdout closed. stderr:\n{self.stderr_path.read_text()}"
                raise AssertionError(msg)
            with self.stdout_path.open("ab") as output:
                output.write(data)
            self.pending += data

    def send(self, *messages: dict[str, Any]) -> None:
        self.send_bytes(
            b"".join(
                json.dumps(message, ensure_ascii=False).encode() + b"\n"
                for message in messages
            )
        )

    def send_bytes(self, data: bytes) -> None:
        assert self.process.stdin is not None
        deadline = time.monotonic() + 10
        offset = 0
        while offset < len(data):
            remaining = deadline - time.monotonic()
            if (
                remaining <= 0
                or not select.select([], [self.process.stdin], [], remaining)[1]
            ):
                msg = "Plugin stopped reading stdin"
                raise AssertionError(msg)
            offset += os.write(
                self.process.stdin.fileno(), data[offset : offset + 4096]
            )

    def receive_sessions(self, *session_ids: str) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {
            session_id: [] for session_id in session_ids
        }
        finished: set[str] = set()
        deadline = time.monotonic() + 10
        while len(finished) < len(session_ids):
            message = self.read_message(deadline)
            if message.get("event") != "session":
                continue
            session_id = message["session_id"]
            assert session_id in results, message
            assert session_id not in finished, message
            results[session_id].append(message["data"])
            if message["data"]["type"] == "end":
                finished.add(session_id)
        return results

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate(timeout=5)
            msg = "Plugin did not exit after SIGTERM"
            raise AssertionError(msg) from None
