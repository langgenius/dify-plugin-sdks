import importlib
import multiprocessing
import socket


def _check_package_import_keeps_standard_socket(queue: multiprocessing.Queue) -> None:
    original_socket = socket.socket
    importlib.import_module("dify_plugin")
    queue.put(socket.socket is original_socket)


def test_package_import_keeps_standard_socket() -> None:
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_check_package_import_keeps_standard_socket,
        args=(queue,),
    )
    process.start()
    process.join(timeout=10)

    assert process.exitcode == 0
    assert queue.get(timeout=1)
