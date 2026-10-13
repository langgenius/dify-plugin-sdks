import inspect
from collections.abc import Callable
from dataclasses import dataclass

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter


@dataclass(frozen=True, slots=True)
class Route:
    filter: Callable[[dict], bool]
    func: Callable[..., object]


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
        filter: Callable[[dict], bool],  # ruff:ignore[builtin-argument-shadowing]
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
                return f(instance, session, annotation(**data))

        else:
            # get first parameter of func
            parameter = parameters[1]
            # get annotation of the first parameter
            annotation = parameter.annotation

            def wrapper(session: Session, data: dict) -> object:
                return f(session, annotation(**data))

        self.routes.append(Route(filter, wrapper))

    def dispatch(self, session: Session, data: dict) -> object | None:
        for route in self.routes:
            if route.filter(data):
                return route.func(session, data)
        return None
