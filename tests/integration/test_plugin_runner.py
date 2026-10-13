import os
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gevent
import pytest
from pydantic import BaseModel, RootModel

from dify_plugin.config.integration_config import IntegrationConfig
from dify_plugin.core.entities.plugin.request import (
    ModelActions,
    ModelInvokeRerankRequest,
    PluginAccessAction,
    PluginInvokeType,
    ToolActions,
    ToolInvokeRequest,
)
from dify_plugin.integration import run as runner_module
from dify_plugin.integration.exc import PluginStoppedError
from dify_plugin.integration.run import PluginRunner

pytestmark = pytest.mark.integration


class Payload(BaseModel):
    value: str


def _invoke(runner: PluginRunner, value: str = "hello") -> Generator[Payload]:
    return runner.invoke(
        PluginInvokeType.Tool,
        ToolActions.InvokeTool,
        payload=Payload(value=value),
        response_type=Payload,
    )


def _assert_pipes_closed(runner: PluginRunner) -> None:
    # gevent defers os.close until the next event loop iteration.
    gevent.sleep(0.001)
    for pipe in (
        runner.stdout_pipe_read,
        runner.stdout_pipe_write,
        runner.stderr_pipe_read,
        runner.stderr_pipe_write,
        runner.stdin_pipe_read,
        runner.stdin_pipe_write,
    ):
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(pipe)


def test_child_exit_unblocks_pending_invocation(local_cli: str) -> None:
    with (
        PluginRunner(
            IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
            "fixture.difypkg",
            extra_args=["--scenario", "exit-on-invoke"],
        ) as runner,
        gevent.Timeout(2, AssertionError("Invocation did not notice child exit")),
        pytest.raises(PluginStoppedError),
    ):
        list(_invoke(runner))


@pytest.mark.parametrize("scenario", ["echo", "mixed", "stderr", "stderr-error"])
def test_runner_reads_local_cli_protocol(local_cli: str, scenario: str) -> None:
    read_pipes: set[int] = set()

    class Runner(PluginRunner):
        def _message_reader(self, pipe: int) -> None:
            assert pipe == self.stdout_pipe_read
            super()._message_reader(pipe)

        def _read_async(self, fd: int) -> bytes:
            read_pipes.add(fd)
            return super()._read_async(fd)

    with (
        Runner(
            IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
            "fixture.difypkg",
            extra_args=["--scenario", scenario],
        ) as runner,
        gevent.Timeout(2, AssertionError("Invocation stopped responding")),
    ):
        assert list(_invoke(runner, "你好")) == [Payload(value="你好")]
        assert read_pipes == {runner.stdout_pipe_read}
        assert runner.process.stdin is None
        assert runner.process.stdout is None
        assert runner.process.stderr is None
    assert runner.process.poll() is not None
    assert not runner.stdout_reader.is_alive()
    _assert_pipes_closed(runner)


@pytest.mark.parametrize(
    ("access_type", "access_action", "payload_type", "payload"),
    [
        (
            PluginInvokeType.Tool,
            ToolActions.InvokeTool,
            ToolInvokeRequest,
            {
                "type": "tool",
                "action": "invoke_tool",
                "user_id": "tool-user",
                "provider": "json_process",
                "tool": "parse",
                "credentials": {"api_key": "tool-key"},
                "credential_type": "api-key",
                "tool_parameters": {
                    "content": '{"message":"你好"}',
                    "ensure_ascii": False,
                    "limit": 0,
                },
            },
        ),
        (
            PluginInvokeType.Model,
            ModelActions.InvokeRerank,
            ModelInvokeRerankRequest,
            {
                "type": "model",
                "action": "invoke_rerank",
                "user_id": "model-user",
                "provider": "openrouter",
                "model_type": "rerank",
                "model": "test-reranker",
                "credentials": {"api_key": "model-key"},
                "query": "capital of France",
                "docs": ["Berlin", "Paris"],
                "score_threshold": None,
                "top_n": 1,
            },
        ),
    ],
    ids=["tool", "model"],
)
def test_runner_preserves_cli_request_fields(
    local_cli: str,
    access_type: PluginInvokeType,
    access_action: PluginAccessAction,
    payload_type: type[BaseModel],
    payload: dict,
) -> None:
    with (
        PluginRunner(
            IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
            "fixture.difypkg",
            extra_args=["--scenario", "record-request"],
        ) as runner,
        gevent.Timeout(2, AssertionError("Invocation stopped responding")),
    ):
        (response,) = runner.invoke(
            access_type,
            access_action,
            payload=payload_type.model_validate(payload),
            response_type=RootModel[dict],
        )
    wire = response.root
    assert wire.pop("invoke_id")
    assert wire == {
        "type": payload["type"],
        "action": payload["action"],
        "request": payload,
    }


def test_runner_routes_interleaved_invocations(local_cli: str) -> None:
    with (
        ThreadPoolExecutor(max_workers=2) as executor,
        PluginRunner(
            IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
            "fixture.difypkg",
            extra_args=["--scenario", "reverse"],
        ) as runner,
        gevent.Timeout(2, AssertionError("Concurrent invocations stopped responding")),
    ):
        results = list(
            executor.map(lambda text: list(_invoke(runner, text)), ["a", "b"])
        )
    assert results == [[Payload(value="a")], [Payload(value="b")]]


@pytest.mark.timeout(5)
def test_timeout_closes_runner_before_waiting_for_invocation_workers(
    local_cli: str,
) -> None:
    with (
        pytest.raises(TimeoutError, match="No invocation response"),
        ThreadPoolExecutor(max_workers=2) as executor,
        PluginRunner(
            IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
            "fixture.difypkg",
            extra_args=["--scenario", "no-response"],
        ) as runner,
        gevent.Timeout(0.1, TimeoutError("No invocation response")),
    ):
        list(executor.map(lambda value: list(_invoke(runner, value)), ["a", "b"]))

    assert runner.process.poll() is not None
    assert not runner.stdout_reader.is_alive()
    assert runner.q == {}


def test_runner_handles_large_requests_and_closed_streams(local_cli: str) -> None:
    with PluginRunner(
        IntegrationConfig(dify_cli_path=local_cli, _env_file=None), "fixture.difypkg"
    ) as runner:
        text = "消息" * 20_000
        with gevent.Timeout(2, AssertionError("Large invocation stopped responding")):
            stream = _invoke(runner, text)
            assert next(stream) == Payload(value=text)
            stream.close()
            assert runner.q == {}
            assert list(_invoke(runner)) == [Payload(value="hello")]
    with pytest.raises(PluginStoppedError):
        list(_invoke(runner))


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("error-on-invoke", "invocation failed"),
        ("invalid-response", "Invalid response type"),
    ],
)
def test_runner_propagates_cli_errors(
    local_cli: str, scenario: str, message: str
) -> None:
    with PluginRunner(
        IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
        "fixture.difypkg",
        extra_args=["--scenario", scenario],
    ) as runner:
        with (
            gevent.Timeout(2, AssertionError("Invocation stopped responding")),
            pytest.raises(ValueError, match=message),
        ):
            list(_invoke(runner))
        assert runner.q == {}


def test_runner_cleans_packaged_source_directory(
    local_cli: str, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with PluginRunner(
        IntegrationConfig(dify_cli_path=local_cli, _env_file=None), str(source)
    ) as runner:
        package = Path(runner.plugin_package_path)
        assert package.read_bytes() == b"local fixture package"
        assert list(_invoke(runner)) == [Payload(value="hello")]
    assert not package.parent.exists()


@pytest.mark.parametrize(
    "scenario", ["exit-before-ready", "error-before-ready", "never-ready"]
)
def test_startup_failure_preserves_timeout_and_reaps_process(
    local_cli: str,
    scenario: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes = []
    pipes = []
    pipe = runner_module.os.pipe
    popen = runner_module.subprocess.Popen

    def record_pipe() -> tuple[int, int]:
        descriptors = pipe()
        pipes.extend(descriptors)
        return descriptors

    def record_process(
        *args: object, **kwargs: object
    ) -> runner_module.subprocess.Popen[bytes]:
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    config = IntegrationConfig(dify_cli_path=local_cli, _env_file=None)
    monkeypatch.setattr(runner_module.os, "pipe", record_pipe)
    monkeypatch.setattr(runner_module.subprocess, "Popen", record_process)
    semaphore = runner_module.Semaphore(0)
    acquire = semaphore.acquire

    def acquire_ready(*, timeout: float) -> bool:
        assert timeout == 30
        return acquire(timeout=0.2)

    monkeypatch.setattr(semaphore, "acquire", acquire_ready)
    monkeypatch.setattr(runner_module, "Semaphore", lambda _value: semaphore)
    with (
        gevent.Timeout(2, AssertionError("Constructor did not notice child exit")),
        pytest.raises(TimeoutError, match="Plugin failed to start within 30 seconds"),
    ):
        PluginRunner(config, "fixture.difypkg", extra_args=["--scenario", scenario])
    assert len(processes) == 1
    assert processes[0].poll() is not None
    gevent.sleep(0.001)
    for fd in pipes[:6]:
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(fd)


def test_packaging_failure_removes_temporary_directory(
    local_cli: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temporary_paths = []
    temporary_directory = runner_module.tempfile.TemporaryDirectory

    def record_directory() -> runner_module.tempfile.TemporaryDirectory[str]:
        directory = temporary_directory()
        temporary_paths.append(Path(directory.name))
        return directory

    source = tmp_path / "fail-package"
    source.mkdir()
    monkeypatch.setattr(runner_module.tempfile, "TemporaryDirectory", record_directory)
    with pytest.raises(runner_module.subprocess.CalledProcessError):
        PluginRunner(
            IntegrationConfig(dify_cli_path=local_cli, _env_file=None), str(source)
        )
    assert len(temporary_paths) == 1
    assert not temporary_paths[0].exists()


def test_runner_waits_for_graceful_shutdown(
    local_cli: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = tmp_path / "allow-shutdown"
    runner = PluginRunner(
        IntegrationConfig(dify_cli_path=local_cli, _env_file=None),
        "fixture.difypkg",
        extra_args=["--scenario", "graceful-termination", str(gate)],
    )
    wait = runner.process.wait

    def wait_for_exit(timeout: float | None = None) -> int:
        assert timeout is None
        return wait(timeout=timeout)

    monkeypatch.setattr(runner.process, "wait", wait_for_exit)
    closing = gevent.spawn(runner._close)
    try:
        with gevent.Timeout(2):
            while not gate.with_suffix(".started").exists():
                gevent.sleep(0.01)
        assert not closing.ready()
        assert runner.process.poll() is None
    finally:
        gate.touch()
        closing.get(timeout=2)
    assert gate.with_suffix(".completed").exists()
    assert runner.process.poll() is not None
    assert not runner.stdout_reader.is_alive()


def test_concurrent_context_exits_wait_for_resource_cleanup(
    local_cli: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runner = PluginRunner(
        IntegrationConfig(dify_cli_path=local_cli, _env_file=None), str(source)
    )
    package = Path(runner.plugin_package_path)
    cleanup_started = threading.Event()
    allow_cleanup = threading.Event()
    wait = runner.process.wait

    def delayed_wait(**kwargs: object) -> int:
        cleanup_started.set()
        assert allow_cleanup.wait(timeout=2)
        return wait(**kwargs)

    monkeypatch.setattr(runner.process, "wait", delayed_wait)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(runner.__exit__, None, None, None)
        assert cleanup_started.wait(timeout=2)
        second = executor.submit(runner.__exit__, None, None, None)
        try:
            with pytest.raises(TimeoutError):
                second.result(timeout=0.05)
        finally:
            allow_cleanup.set()
            first.result(timeout=2)
            second.result(timeout=2)
    assert runner.process.poll() is not None
    assert not runner.stdout_reader.is_alive()
    _assert_pipes_closed(runner)
    assert not package.parent.exists()


def test_reader_start_failure_keeps_original_error(
    local_cli: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = IntegrationConfig(dify_cli_path=local_cli, _env_file=None)

    def fail_start(_thread: threading.Thread) -> None:
        msg = "reader start failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(runner_module.threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="reader start failed"):
        PluginRunner(config, "fixture.difypkg")
