import inspect
import logging
from collections.abc import Callable
from typing import Any, Optional

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter

logger = logging.getLogger(__file__)


class Route:
    filter: Callable[[dict], bool]
    func: Callable

    def __init__(self, filter: Callable[[dict], bool], func) -> None:  # noqa: A002
        self.filter = filter
        self.func = func


class Router:
    routes: list[Route]
    request_reader: RequestReader

    def __init__(self, request_reader: RequestReader, response_writer: Optional[ResponseWriter]) -> None:
        self.routes = []
        self.request_reader = request_reader
        self.response_writer = response_writer

    def register_route(self, f: Callable, filter: Callable[[dict], bool], instance: Any = None):  # noqa: A002
        sig = inspect.signature(f)
        parameters = list(sig.parameters.values())
        if len(parameters) == 0:
            raise ValueError("Route function must have at least one parameter")

        if instance:
            # get first parameter of func
            parameter = parameters[2]
            # get annotation of the first parameter
            annotation = parameter.annotation

            def wrapper(session: Session, data: dict):
                try:
                    data = annotation(**data)
                except TypeError as e:
                    if not self.response_writer:
                        logger.exception("failed to route request: %s")
                    else:
                        self.response_writer.error(
                            session_id=session.session_id,
                            data={"error": str(e), "error_type": type(e).__name__},
                        )
                return f(instance, session, data)
        else:
            # get first parameter of func
            parameter = parameters[1]
            # get annotation of the first parameter
            annotation = parameter.annotation

            def wrapper(session: Session, data: dict):
                try:
                    data = annotation(**data)
                except TypeError as e:
                    if not self.response_writer:
                        logger.exception("failed to route request: %s")
                    else:
                        self.response_writer.error(
                            session_id=session.session_id,
                            data={"error": str(e), "error_type": type(e).__name__},
                        )
                return f(session, data)

        self.routes.append(Route(filter, wrapper))

    def dispatch(self, session: Session, data: dict) -> Any:
        for route in self.routes:
            if route.filter(data):
                return route.func(session, data)
