from pathlib import Path

import pytest

from dify_plugin.core.utils.yaml_loader import load_yaml_file


def test_load_yaml_preserves_unicode_and_nested_values(tmp_path: Path) -> None:
    file_path = tmp_path / "provider.yaml"
    file_path.write_text("label: 你好\nconfig:\n  enabled: true\n  retries: 0\n")

    assert load_yaml_file(str(file_path)) == {
        "label": "你好",
        "config": {"enabled": True, "retries": 0},
    }


def test_cyclic_symlink_raises_by_default(tmp_path: Path) -> None:
    file_path = tmp_path / "loop.yaml"
    file_path.symlink_to(file_path)

    with pytest.raises(FileNotFoundError):
        load_yaml_file(str(file_path))


def test_missing_file_respects_ignore_error(tmp_path: Path) -> None:
    file_path = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError):
        load_yaml_file(str(file_path))

    assert load_yaml_file(str(file_path), ignore_error=True) == {}


def test_ignore_error_covers_path_probe_errors(tmp_path: Path) -> None:
    file_path = tmp_path / ("x" * 5000)

    assert load_yaml_file(str(file_path), ignore_error=True) == {}
