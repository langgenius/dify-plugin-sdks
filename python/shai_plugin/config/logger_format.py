import json
import logging
import sys


class ShaiPluginLoggerFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "event": "log",
                "data": {
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "timestamp": record.created,
                },
            }
        )


plugin_logger_handler = logging.StreamHandler(sys.stdout)
plugin_logger_handler.setLevel(logging.INFO)
plugin_logger_handler.setFormatter(ShaiPluginLoggerFormatter())
