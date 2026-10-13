import sys
from abc import ABC
from collections.abc import Generator
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest

from dify_plugin.core.utils.class_loader import (
    get_subclasses_from_module,
    import_module_from_source,
    load_multi_subclasses_from_source,
    load_single_subclass_from_source,
)


@pytest.fixture
def module_name() -> Generator[str, None, None]:
    name = f"test_plugin_{uuid4().hex}"
    try:
        yield name
    finally:
        sys.modules.pop(name, None)


def test_imports_source_and_registers_module(tmp_path: Path, module_name: str) -> None:
    source = tmp_path / "plugin.py"
    source.write_text("VALUE = 'loaded'\n", encoding="utf-8")

    module = import_module_from_source(
        module_name=module_name, py_file_path=str(source)
    )

    assert module.VALUE == "loaded"
    assert sys.modules[module_name] is module


def test_lazy_source_runs_when_first_accessed(tmp_path: Path, module_name: str) -> None:
    source = tmp_path / "plugin.py"
    source.write_text(
        "from pathlib import Path\n"
        "Path(__file__).with_suffix('.loaded').write_text('ready', encoding='utf-8')\n"
        "VALUE = 42\n",
        encoding="utf-8",
    )

    module = import_module_from_source(
        module_name=module_name, py_file_path=str(source), use_lazy_loader=True
    )

    assert not source.with_suffix(".loaded").exists()
    assert module.VALUE == 42
    assert source.with_suffix(".loaded").read_text(encoding="utf-8") == "ready"


def test_module_discoverable_on_python_path_loads(
    tmp_path: Path, module_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / f"{module_name}.py"
    source.write_text("VALUE = 42\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    module = import_module_from_source(
        module_name=module_name, py_file_path=str(source)
    )

    assert module.VALUE == 42


def test_module_without_source_loader_reports_path(
    tmp_path: Path, module_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    namespace = tmp_path / module_name
    namespace.mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(Exception, match=f"Failed to load module {module_name}"):
        import_module_from_source(module_name=module_name, py_file_path=str(namespace))


def test_unsupported_source_path_reports_module(
    tmp_path: Path, module_name: str
) -> None:
    source = tmp_path / "plugin.txt"
    source.write_text("VALUE = 42\n", encoding="utf-8")

    with pytest.raises(Exception, match=f"Failed to load module {module_name}"):
        import_module_from_source(module_name=module_name, py_file_path=str(source))


@pytest.mark.parametrize(
    ("source_text", "error_type", "message"),
    [
        ("class Broken(\n", SyntaxError, "never closed"),
        ("raise RuntimeError('plugin failed')\n", RuntimeError, "plugin failed"),
    ],
)
def test_source_errors_reach_caller(
    tmp_path: Path,
    module_name: str,
    source_text: str,
    error_type: type[Exception],
    message: str,
) -> None:
    source = tmp_path / "plugin.py"
    source.write_text(source_text, encoding="utf-8")

    with pytest.raises(error_type, match=message):
        import_module_from_source(module_name=module_name, py_file_path=str(source))


def test_subclass_discovery_excludes_parent_instances_and_unrelated_types() -> None:
    class Parent:
        pass

    class Child(Parent):
        pass

    class Grandchild(Child):
        pass

    module = ModuleType("plugin")
    module.Parent = Parent
    module.Child = Child
    module.Grandchild = Grandchild
    module.Unrelated = str
    module.instance = Child()

    assert get_subclasses_from_module(module, Parent) == [Child, Grandchild]


@pytest.mark.parametrize("lazy", [False, True])
def test_loads_multiple_plugin_classes(
    tmp_path: Path, module_name: str, lazy: bool
) -> None:
    source = tmp_path / "plugin.py"
    source.write_text(
        "from abc import ABC\nclass Alpha(ABC): pass\nclass Beta(ABC): pass\n",
        encoding="utf-8",
    )

    classes = load_multi_subclasses_from_source(
        module_name=module_name,
        script_path=str(source),
        parent_type=ABC,
        use_lazy_loader=lazy,
    )

    assert [cls.__name__ for cls in classes] == ["Alpha", "Beta"]
    assert all(issubclass(cls, ABC) for cls in classes)


@pytest.mark.parametrize(
    ("definitions", "error"),
    [
        ("", "Missing subclass of ABC"),
        (
            "class Alpha(ABC): pass\nclass Beta(ABC): pass\n",
            "Multiple subclasses of ABC",
        ),
    ],
)
def test_single_plugin_class_rejects_missing_or_ambiguous_implementations(
    tmp_path: Path, module_name: str, definitions: str, error: str
) -> None:
    source = tmp_path / "plugin.py"
    source.write_text(f"from abc import ABC\n{definitions}", encoding="utf-8")

    with pytest.raises(Exception, match=error):
        load_single_subclass_from_source(
            module_name=module_name, script_path=str(source), parent_type=ABC
        )


def test_single_plugin_class_can_be_instantiated(
    tmp_path: Path, module_name: str
) -> None:
    source = tmp_path / "plugin.py"
    source.write_text(
        "from abc import ABC\nclass Plugin(ABC): VALUE = 42\n", encoding="utf-8"
    )

    implementation = load_single_subclass_from_source(
        module_name=module_name, script_path=str(source), parent_type=ABC
    )

    assert implementation().VALUE == 42
