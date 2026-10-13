import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from dify_plugin.config.integration_config import IntegrationConfig, find_dify_cli_path


def write_cli(tmp_path: Path, name: str, version: str) -> Path:
    cli = tmp_path / name
    cli.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "assert sys.argv[1:] == ['version']\n"
        f"print({version!r})\n"
    )
    cli.chmod(0o700)
    return cli


@pytest.fixture(autouse=True)
def isolated_cli_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DIFY_CLI_PATH", raising=False)
    monkeypatch.delenv("dify_cli_path", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))


@pytest.mark.parametrize("name", ["dify", "dify-plugin", "dify-plugin-linux-amd64"])
def test_cli_is_discovered_on_path_and_version_is_checked(
    tmp_path: Path, name: str
) -> None:
    cli = write_cli(tmp_path, name, "0.1.0")

    assert find_dify_cli_path() == str(cli)
    assert IntegrationConfig(_env_file=None).dify_cli_path == str(cli)


def test_explicit_cli_overrides_environment_and_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_cli(tmp_path, "dify", "0.0.1")
    environment_cli = write_cli(tmp_path, "environment-cli", "0.1.0")
    explicit_cli = write_cli(tmp_path, "explicit-cli", "0.2.0")
    monkeypatch.setenv("DIFY_CLI_PATH", str(environment_cli))

    assert find_dify_cli_path() == str(environment_cli)
    assert IntegrationConfig(_env_file=None).dify_cli_path == str(environment_cli)
    assert IntegrationConfig(
        dify_cli_path=str(explicit_cli), _env_file=None
    ).dify_cli_path == str(explicit_cli)


def test_missing_cli_has_actionable_configuration_error() -> None:
    assert find_dify_cli_path() is None
    with pytest.raises(ValidationError, match="dify cli not found"):
        IntegrationConfig(_env_file=None)


@pytest.mark.parametrize("version", ["0.1.0\n", "0.1.1.dev1", "1.0.0"])
def test_cli_accepts_supported_versions(tmp_path: Path, version: str) -> None:
    cli = write_cli(tmp_path, "custom-cli", version)

    assert IntegrationConfig(
        dify_cli_path=str(cli), _env_file=None
    ).dify_cli_path == str(cli)


@pytest.mark.parametrize(
    ("version", "message"),
    [
        ("0.0.9", "to support plugin run"),
        ("0.1.0rc1", "to support plugin run"),
        ("unparseable version", "version is not valid"),
    ],
)
def test_cli_rejects_unsupported_or_invalid_version(
    tmp_path: Path, version: str, message: str
) -> None:
    cli = write_cli(tmp_path, "custom-cli", version)

    with pytest.raises(ValidationError, match=message):
        IntegrationConfig(dify_cli_path=str(cli), _env_file=None)
