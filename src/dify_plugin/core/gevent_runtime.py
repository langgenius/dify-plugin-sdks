"""Whether this runtime can interrupt a greenlet blocked in IO.

Enforcement that relies on an asynchronous raise -- a first-token deadline, a cancel --
only works once gevent has patched the socket module. Everything that depends on it must
degrade to no enforcement rather than to a wrong answer, so the predicate lives in one
place and is read at call time.
"""

import socket

import gevent.socket


def interruptible() -> bool:
    """True when a blocking call can be interrupted by an asynchronous raise."""
    return socket.socket is gevent.socket.socket
