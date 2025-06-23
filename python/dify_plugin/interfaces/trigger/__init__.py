from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, final

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities import ParameterOption
from dify_plugin.entities.trigger import TriggerResponse, TriggerRuntime


class TriggerProvider:
    """
    The provider of a trigger
    """

    def validate_credentials(self, credentials: dict):
        return self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: dict):
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        return self._oauth_get_authorization_url(system_credentials)

    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        return self._oauth_get_credentials(system_credentials, request)

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        raise NotImplementedError("This method should be implemented by a subclass")


class Trigger(ABC):
    """
    The trigger interface
    """

    runtime: TriggerRuntime
    session: Session

    @final
    def __init__(
        self,
        runtime: TriggerRuntime,
        session: Session,
    ):
        """
        Initialize the trigger

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.runtime = runtime
        self.session = session

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _trigger(self, request: Request, values: Mapping, parameters: Mapping) -> TriggerResponse:
        """
        Trigger the trigger with the given request.

        To be implemented by subclasses.
        """

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.

        To be implemented by subclasses.

        Also, it's optional to implement, that's why it's not an abstract method.
        """
        raise NotImplementedError("This method should be implemented by a subclass")

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def trigger(self, request: Request, values: Mapping, parameters: Mapping) -> TriggerResponse:
        """
        Trigger the trigger with the given request.
        """
        return self._trigger(request, values, parameters)

    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        return self._fetch_parameter_options(parameter)
