from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, final

from werkzeug import Request

from dify_plugin.entities import ParameterOption
from dify_plugin.entities.trigger import (
    Variables,
)

from .runtime import EventRuntime


class Event(ABC):
    """
    Base class for events that transform incoming webhook payloads into
    workflow variables.

    An Event receives a raw webhook request and transforms it into structured Variables
    that can be consumed by workflows. Each event implements:
    1. Data transformation from provider-specific format to standard output
    2. Filtering logic based on user-defined parameters
    3. Parameter validation and option fetching

    Responsibilities:
    - Parse and validate webhook payload
    - Apply user-configured filters (e.g., label filters, author filters)
    - Extract and transform data into output_schema format
    - Return structured Variables with extracted data

    Example implementations:
    - IssueOpenedEvent: Transforms GitHub issue webhook into workflow variables
    - MessageTextEvent: Transforms WhatsApp message webhook into workflow variables

    Workflow:
    1. Trigger receives webhook → dispatch_event() → returns Event names
    2. Dify invokes the specified Event → _on_event() → returns Variables
    3. Variables are passed to the workflow for processing
    """

    # Optional context objects. They may be None in environments like schema generation
    # or static validation where execution context isn't initialized.
    runtime: EventRuntime

    @final
    def __init__(
        self,
        runtime: EventRuntime,
    ) -> None:
        """
        Initialize the Event.

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        - The `runtime` parameter may be None in contexts where execution
          is not happening (e.g., schema generation, documentation generation).
        """
        self.runtime = runtime

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Transform the incoming webhook request into structured Variables.

        This method should:
        1. Parse the webhook payload from the request
        2. Apply filtering logic based on parameters
        3. Extract relevant data matching the output_schema
        4. Return a structured Variables object

        Args:
            request: The incoming webhook HTTP request containing the raw payload.
                    Use request.get_json() to parse JSON body.
            parameters: User-configured parameters for filtering and transformation
                       (e.g., label filters, regex patterns, threshold values).
                       These come from the subscription configuration.
            payload: The decoded payload from previous step `Trigger.dispatch_event`.
                     It will be delivered into `_on_event` method.
        Returns:
            Variables: Structured variables matching the output_schema
                      defined in the event's YAML configuration.

        Raises:
            EventIgnoreError: When the event should be filtered out based on parameters
            ValueError: When the payload is invalid or missing required fields

        Example:
            >>> def _on_event(self, request, parameters):
            ...     payload = request.get_json()
            ...
            ...     # Apply filters
            ...     if not self._matches_filters(payload, parameters):
            ...         raise EventIgnoreError()
            ...
            ...     # Transform data
            ...     return Variables(variables={
            ...         "title": payload["issue"]["title"],
            ...         "author": payload["issue"]["user"]["login"],
            ...         "url": payload["issue"]["html_url"],
            ...     })
        """

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.

        To be implemented by subclasses.

        Also, it's optional to implement, that's why it's not an abstract method.
        """
        msg = (
            "This plugin should implement `_fetch_parameter_options` method "
            "to enable dynamic select parameter"
        )
        raise NotImplementedError(msg)

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Process the event with the given request.
        """
        return self._on_event(request=request, parameters=parameters, payload=payload)

    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        return self._fetch_parameter_options(parameter=parameter)
