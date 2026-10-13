"""Emulate the CLI JSON boundary for PluginRunner process tests."""

import json
import signal
import sys
from pathlib import Path
from typing import Any, TextIO


def emit(
    event: str,
    invoke_id: str = "",
    response: dict[str, Any] | None = None,
    output: TextIO = sys.stdout,
) -> None:
    output.write(
        json.dumps({"invoke_id": invoke_id, "type": event, "response": response or {}})
        + "\n"
    )
    output.flush()


def respond(request: dict[str, Any]) -> None:
    emit("plugin_response", request["invoke_id"], request["request"])
    emit("plugin_invoke_end", request["invoke_id"], {"info": "plugin invoke end"})


def main() -> None:
    if sys.argv[1:] == ["version"]:
        sys.stdout.write("0.1.0\n")
        return
    if sys.argv[1:3] == ["plugin", "package"]:
        if Path(sys.argv[3]).name == "fail-package":
            sys.stderr.write("package failed\n")
            raise SystemExit(1)
        Path(sys.argv[5]).write_bytes(b"local fixture package")
        return

    scenario = sys.argv[7] if sys.argv[6:7] == ["--scenario"] else "echo"
    if scenario == "exit-before-ready":
        return
    if scenario == "error-before-ready":
        emit("error", response={"error": "startup failed"})
        return
    if scenario == "ignore-termination":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if scenario == "never-ready":
        sys.stdin.read()
        return
    emit("plugin_ready", response={"info": "plugin loaded"})
    if scenario == "stderr":
        emit("info", response={"info": "x" * 200_000}, output=sys.stderr)

    pending = []
    for line in sys.stdin:
        request = json.loads(line)
        if scenario == "exit-on-invoke":
            return
        if scenario == "error-on-invoke":
            # The CLI emits no end frame when invocation setup fails.
            emit("error", request["invoke_id"], {"error": "invocation failed"})
        elif scenario == "record-request":
            emit("plugin_response", request["invoke_id"], request)
            emit(
                "plugin_invoke_end", request["invoke_id"], {"info": "plugin invoke end"}
            )
        elif scenario == "invalid-response":
            emit("info", request["invoke_id"])
        elif scenario == "mixed":
            sys.stdout.write("\nnot json\n")
            emit("info", response={"info": "fixture log"})
            emit("plugin_response", "unknown-invocation", {"value": "ignored"})
            respond(request)
        elif scenario == "no-response":
            continue
        elif scenario == "reverse":
            pending.append(request)
            if len(pending) == 2:
                for item in reversed(pending):
                    respond(item)
                pending.clear()
        else:
            respond(request)


if __name__ == "__main__":
    main()
