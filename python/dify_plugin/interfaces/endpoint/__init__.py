from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import final

from werkzeug import Request, Response

from dify_plugin.core.runtime import Session


class EndpointGroup(ABC):
    def setup(self, settings: Mapping):
        return self._setup(settings)

    @abstractmethod
    def _setup(self, settings: Mapping):
        pass


class Endpoint(ABC):
    @final
    def __init__(self, session: Session) -> None:
        """
        Initialize the endpoint

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.session = session

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.

        To be implemented by subclasses.
        """

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.
        """
        return self._invoke(r, values, settings)
