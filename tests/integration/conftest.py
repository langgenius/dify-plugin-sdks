import json
import os
import shutil
import subprocess  # ruff:ignore[suspicious-subprocess-import]
import sys
import time
import tomllib
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from coverage import Coverage

from .stdio import StdioPlugin

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "plugins" / "contract_plugin"


def _package_files(directory: Path) -> set[Path]:
    return {
        path.relative_to(directory)
        for path in directory.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    }


@pytest.fixture
def local_cli(tmp_path: Path) -> str:
    path = tmp_path / "dify-plugin"
    source = PROJECT_ROOT / "tests" / "fixtures" / "plugin_cli.py"
    path.write_text(f"#!{sys.executable}\n" + source.read_text())
    path.chmod(0o700)
    return str(path)


@pytest.fixture(scope="session")
def installed_sdk(tmp_path_factory: pytest.TempPathFactory) -> Path:
    build_dir = tmp_path_factory.mktemp("sdk-wheel")
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build and install the SDK under test"
    subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]
        [uv, "build", "--wheel", "--offline", "--out-dir", str(build_dir)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    wheels = list(build_dir.glob("*.whl"))
    assert len(wheels) == 1
    install_dir = build_dir / "site-packages"
    subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]
        [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--offline",
            "--no-deps",
            "--target",
            str(install_dir),
            str(wheels[0]),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    source_package = PROJECT_ROOT / "src" / "dify_plugin"
    installed_package = install_dir / "dify_plugin"
    source_files = _package_files(source_package)
    assert _package_files(installed_package) == source_files
    for relative_path in source_files:
        assert (installed_package / relative_path).read_bytes() == (
            source_package / relative_path
        ).read_bytes(), relative_path
    return install_dir


@pytest.fixture
def stdio_plugin(installed_sdk: Path, tmp_path: Path) -> Generator[StdioPlugin]:
    plugin_dir = tmp_path / "plugin"
    shutil.copytree(
        PLUGIN_ROOT, plugin_dir, ignore=shutil.ignore_patterns("__pycache__")
    )
    manifest_path = plugin_dir / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    # The daemon permits tools and endpoints together, but other kinds are exclusive.
    manifest["plugins"] = {
        kind: manifest["plugins"][kind] for kind in ("tools", "endpoints")
    }
    manifest_path.write_text(yaml.safe_dump(manifest))
    stderr_path = tmp_path / "plugin.stderr"
    env = {**os.environ, "PYTHONPATH": str(installed_sdk), "PYTHONNOUSERSITE": "1"}
    env.pop("PYTHONUNBUFFERED", None)
    with stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            [sys.executable, "-m", "main"],
            cwd=plugin_dir,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
        )
        plugin = StdioPlugin(process, stderr_path)
        try:
            deadline = time.monotonic() + 10
            plugin.manifest = plugin.read_message(deadline)
            assert plugin.manifest["name"] == "contract_plugin"
            while plugin.read_message(deadline).get("event") != "heartbeat":
                pass
            identity = json.loads(stderr_path.read_text().splitlines()[0])
            sdk_file = Path(identity["sdk_file"])
            assert sdk_file == installed_sdk / "dify_plugin" / "__init__.py"
            project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
            assert identity["sdk_version"] == project["project"]["version"]
            if Coverage.current() is not None:
                assert identity["coverage_active"], "Plugin coverage did not start"
            yield plugin
        finally:
            plugin.close()
