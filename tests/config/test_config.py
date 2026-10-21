from pathlib import Path

import pytest
from pydantic import ValidationError

from dify_plugin.config.config import DifyPluginEnv, InstallMethod


@pytest.fixture(autouse=True)  # ruff: ignore[pytest-fixture-autouse]
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in DifyPluginEnv.model_fields:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.chdir(tmp_path)


def test_launch_defaults_to_local_install_without_dotenv() -> None:
    env = DifyPluginEnv()

    assert InstallMethod.Local == env.INSTALL_METHOD
    assert env.REMOTE_INSTALL_URL is None
    assert env.REMOTE_INSTALL_KEY is None
    assert env.MAX_REQUEST_TIMEOUT > env.MAX_INVOCATION_TIMEOUT > 0


@pytest.mark.parametrize("method", list(InstallMethod))
def test_process_environment_selects_install_method_and_parses_limits(
    monkeypatch: pytest.MonkeyPatch, method: InstallMethod
) -> None:
    monkeypatch.setenv("INSTALL_METHOD", method.value)
    monkeypatch.setenv("REMOTE_INSTALL_URL", "127.0.0.1:9001")
    monkeypatch.setenv("REMOTE_INSTALL_PORT", "9001")
    monkeypatch.setenv("SERVERLESS_PORT", "9002")
    monkeypatch.setenv("MAX_REQUEST_TIMEOUT", "7200")
    monkeypatch.setenv("MAX_INVOCATION_TIMEOUT", "3700")
    monkeypatch.setenv("MAX_WORKER", "3")
    monkeypatch.setenv("HEARTBEAT_INTERVAL", "0.25")

    env = DifyPluginEnv()

    assert method == env.INSTALL_METHOD
    assert env.REMOTE_INSTALL_URL == "127.0.0.1:9001"
    assert env.REMOTE_INSTALL_PORT == 9001
    assert env.SERVERLESS_PORT == 9002
    assert env.MAX_REQUEST_TIMEOUT == 7200
    assert env.MAX_INVOCATION_TIMEOUT == 3700
    assert env.MAX_WORKER == 3
    assert pytest.approx(0.25) == env.HEARTBEAT_INTERVAL


def test_constructor_overrides_environment_which_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "INSTALL_METHOD=remote\n"
        "REMOTE_INSTALL_HOST=dotenv.example\n"
        "REMOTE_INSTALL_PORT=5004\n"
        "MAX_WORKER=2\n"
        "PLUGIN_DESCRIPTION=中文\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("INSTALL_METHOD", "serverless")
    monkeypatch.setenv("REMOTE_INSTALL_PORT", "9001")
    monkeypatch.setenv("MAX_WORKER", "3")

    env = DifyPluginEnv(MAX_WORKER=4)

    assert InstallMethod.Serverless == env.INSTALL_METHOD
    assert env.REMOTE_INSTALL_HOST == "dotenv.example"
    assert env.REMOTE_INSTALL_PORT == 9001
    assert env.MAX_WORKER == 4
    assert "PLUGIN_DESCRIPTION" not in env.model_dump()


@pytest.mark.parametrize(
    ("name", "value"),
    [("INSTALL_METHOD", "unknown"), ("MAX_INVOCATION_TIMEOUT", "not-a-number")],
)
def test_invalid_environment_fails_before_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match=name):
        DifyPluginEnv()


def test_settings_cannot_change_after_initialization() -> None:
    env = DifyPluginEnv(MAX_WORKER=3)

    with pytest.raises(ValidationError, match="frozen"):
        env.MAX_WORKER = 4
    assert env.MAX_WORKER == 3
