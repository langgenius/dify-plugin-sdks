import inspect
import logging
from collections.abc import Callable

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter

logger = logging.getLogger(__name__)


class Route:
    filter: Callable[[dict], bool]
    func: Callable[..., object]

    def __init__(
        self,
        filter: Callable[[dict], bool],  # noqa: A002
        func: Callable[..., object],
    ) -> None:
        self.filter = filter
        self.func = func


class Router:
    routes: list[Route]
    request_reader: RequestReader

    def __init__(
        self, request_reader: RequestReader, response_writer: ResponseWriter | None
    ) -> None:
        self.routes = []
        self.request_reader = request_reader
        self.response_writer = response_writer

    def register_route(
        self,
        f: Callable[..., object],
        filter: Callable[[dict], bool],  # noqa: A002
        instance: object | None = None,
    ) -> None:
        sig = inspect.signature(f)
        parameters = list(sig.parameters.values())
        if len(parameters) == 0:
            msg = "Route function must have at least one parameter"
            raise ValueError(msg)

        if instance:
            # get first parameter of func
            parameter = parameters[2]
            # get annotation of the first parameter
            annotation = parameter.annotation

            def wrapper(session: Session, data: dict) -> object:
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

            def wrapper(session: Session, data: dict) -> object:
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

    def dispatch(self, session: Session, data: dict) -> object | None:
        for route in self.routes:
            if route.filter(data):
                return route.func(session, data)
        return None
