from pathlib import Path

import pytest
import yaml

from dify_plugin.core.utils import yaml_loader as yaml_loader_module
from dify_plugin.core.utils.yaml_loader import load_yaml_file


class SwitchingPath:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths
        self.calls = 0

    def __fspath__(self) -> str:
        path = self.paths[self.calls]
        self.calls += 1
        return str(path)


class UnstringableMissingPath:
    def __init__(self, file_path: Path, error: RuntimeError) -> None:
        self.file_path = file_path
        self.error = error

    def __fspath__(self) -> str:
        return str(self.file_path)

    def __str__(self) -> str:
        raise self.error


class MissingYamlError(FileNotFoundError, yaml.YAMLError):
    pass


def test_cyclic_symlink_keeps_missing_file_behavior(tmp_path: Path) -> None:
    file_path = tmp_path / "loop.yaml"
    file_path.symlink_to(file_path)

    assert load_yaml_file(str(file_path)) == {}


def test_ignore_error_covers_path_probe_errors(tmp_path: Path) -> None:
    file_path = tmp_path / ("x" * 5000)

    assert load_yaml_file(str(file_path), ignore_error=True) == {}


def test_pathlike_is_resolved_for_exists_and_open(tmp_path: Path) -> None:
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    first_path.write_text("source: first", encoding="utf-8")
    second_path.write_text("source: second", encoding="utf-8")
    file_path = SwitchingPath([first_path, second_path])

    assert load_yaml_file(file_path) == {"source": "second"}
    assert file_path.calls == 2


def test_missing_path_preserves_string_conversion_error(tmp_path: Path) -> None:
    error = RuntimeError()
    file_path = UnstringableMissingPath(tmp_path / "missing.yaml", error)

    with pytest.raises(RuntimeError) as exc_info:
        load_yaml_file(file_path)

    assert exc_info.value is error


def test_missing_file_errors_take_precedence_over_yaml_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MissingYamlError()
    monkeypatch.setattr(
        yaml_loader_module,
        "_read_yaml_file",
        lambda _file_path: (_ for _ in ()).throw(error),
    )

    assert load_yaml_file("missing.yaml") == {}
