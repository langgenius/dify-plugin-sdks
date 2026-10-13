import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from pathlib import Path

import pytest

from dify_plugin import cli
from dify_plugin.commands import generate_docs


def test_documentation_command_writes_in_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    generate_docs()

    document = (tmp_path / "docs.md").read_text(encoding="utf-8")
    assert document.startswith("# Dify Plugin SDK Schema Documentation\n")
    assert "## Manifest\n" in document
    assert "## Table of Contents\n" in document


def test_cli_dispatches_generate_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["dify-plugin", "generate-docs"])

    cli.main()

    assert "## Manifest\n" in (tmp_path / "docs.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("arguments", [[], ["unknown-command"]])
def test_cli_rejects_missing_or_unknown_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["dify-plugin", *arguments])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "generate-docs" in capsys.readouterr().err
    assert not (tmp_path / "docs.md").exists()


def test_module_entrypoint_prints_help_without_generating_docs(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dify_plugin.cli", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert "generate-docs" in result.stdout
    assert not (tmp_path / "docs.md").exists()
