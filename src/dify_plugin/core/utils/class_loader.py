import importlib.util
import sys
from types import ModuleType


def import_module_from_source(
    *, module_name: str, py_file_path: str | bytes, use_lazy_loader: bool = False
) -> ModuleType:
    """
    Importing a module from the source file directly
    """
    try:
        existed_spec = importlib.util.find_spec(module_name)
        if existed_spec:
            spec = existed_spec
            if not spec.loader:
                raise Exception(
                    f"Failed to load module {module_name} from {py_file_path}"
                )
        else:
            # Refer to: https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
            spec = importlib.util.spec_from_file_location(module_name, py_file_path)
            if not spec or not spec.loader:
                raise Exception(
                    f"Failed to load module {module_name} from {py_file_path}"
                )
            if use_lazy_loader:
                # Refer to: https://docs.python.org/3/library/importlib.html#implementing-lazy-imports
                spec.loader = importlib.util.LazyLoader(spec.loader)
        module = importlib.util.module_from_spec(spec)
        if not existed_spec:
            sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        raise


def get_subclasses_from_module[T](
    mod: ModuleType, parent_type: type[T]
) -> list[type[T]]:
    """
    Get all the subclasses of the parent type from the module
    """
    return [
        x
        for x in vars(mod).values()
        if isinstance(x, type) and x != parent_type and issubclass(x, parent_type)
    ]


def load_multi_subclasses_from_source[T](
    *,
    module_name: str,
    script_path: str | bytes,
    parent_type: type[T],
    use_lazy_loader: bool = False,
) -> list[type[T]]:
    """
    Load multiple subclasses from the source
    """
    module = import_module_from_source(
        module_name=module_name,
        py_file_path=script_path,
        use_lazy_loader=use_lazy_loader,
    )
    return get_subclasses_from_module(module, parent_type)


def load_single_subclass_from_source[T](
    *,
    module_name: str,
    script_path: str | bytes,
    parent_type: type[T],
    use_lazy_loader: bool = False,
) -> type[T]:
    """
    Load a single subclass from the source
    """
    module = import_module_from_source(
        module_name=module_name,
        py_file_path=script_path,
        use_lazy_loader=use_lazy_loader,
    )
    subclasses = get_subclasses_from_module(module, parent_type)
    match len(subclasses):
        case 1:
            return subclasses[0]
        case 0:
            raise Exception(
                f"Missing subclass of {parent_type.__name__} in {script_path}"
            )
        case _:
            raise Exception(
                f"Multiple subclasses of {parent_type.__name__} in {script_path}"
            )
