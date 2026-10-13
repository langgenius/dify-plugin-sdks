import json
import sys
from importlib.metadata import version

from coverage import Coverage

import dify_plugin
from dify_plugin import DifyPluginEnv, Plugin

if __name__ == "__main__":
    sys.stderr.write(
        json.dumps({
            "sdk_file": dify_plugin.__file__,
            "sdk_version": version("dify-plugin"),
            "coverage_active": Coverage.current() is not None,
        })
        + "\n"
    )
    sys.stderr.flush()
    Plugin(
        DifyPluginEnv(
            INSTALL_METHOD="local", MAX_WORKER=4, HEARTBEAT_INTERVAL=60, _env_file=None
        )
    ).run()
