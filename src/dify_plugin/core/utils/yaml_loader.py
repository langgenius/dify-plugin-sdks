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
        if True, return empty dict if error occurs and the error will be
        logged in warning level
        if False, raise error if error occurs
    :return: a dict of the YAML content

    Returns:
        The return value.

    Raises:
        FileNotFoundError: If the YAML file cannot be loaded.
        YAMLError: If the YAML file cannot be loaded.
    """
    try:
        if not file_path or not pathlib.Path(file_path).exists():
            raise FileNotFoundError(
                f"Failed to load YAML file {file_path}: file not found",
            )

        with pathlib.Path(file_path).open(encoding="utf-8") as file:
            try:
                return yaml.safe_load(file)
            except Exception as e:
                raise yaml.YAMLError(
                    f"Failed to load YAML file {file_path}: {e}",
                ) from e
    except FileNotFoundError as e:
        logger.debug("Failed to load YAML file %s: %s", file_path, e)
        return {}
    except Exception:
        if ignore_error:
            logger.exception("Failed to load YAML file %s", file_path)
            return {}
        raise
