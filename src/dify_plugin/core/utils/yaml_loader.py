import logging
import pathlib
from typing import Any

import yaml

from dify_plugin.config.logger_format import plugin_logger_handler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)


def load_yaml_file(file_path: str, ignore_error: bool = False) -> dict[str, Any]:
    """Safe loading a YAML file to a dict
    :param file_path: the path of the YAML file
    :param ignore_error:
        if True, return an empty dict when loading fails
        if False, raise loading errors; missing files still return an empty dict
    :return: a dict of the YAML content

    Returns:
        The return value.

    Raises:
        YAMLError: If the YAML file cannot be loaded.
    """
    if not file_path:
        logger.debug("Failed to load YAML file %s: file not found", file_path)
        return {}

    try:
        with pathlib.Path(file_path).open(encoding="utf-8") as file:
            try:
                return yaml.safe_load(file)
            except Exception as e:
                msg = f"Failed to load YAML file {file_path}: {e}"
                raise yaml.YAMLError(msg) from e
    except FileNotFoundError as e:
        logger.debug("Failed to load YAML file %s: %s", file_path, e)
        return {}
    except Exception:
        if ignore_error:
            logger.exception("Failed to load YAML file %s", file_path)
            return {}
        raise
