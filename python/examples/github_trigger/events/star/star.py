from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class StarCreatedEvent(Event):
    """
    GitHub Star Created Event

    This event transforms GitHub star created webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub star created webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        star_action = payload.get("action")
        events = parameters.get("events", [])
        if star_action not in events:
            raise EventIgnoreError("Not interested in this star action " + star_action)

        sender = payload.get("sender")
        if not sender:
            raise ValueError("No sender data in payload")
        return Variables(variables={**payload})

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """Fetch parameter options"""

        # 1. through the credentials for auto created only plugins
        if self.runtime.credential_type == CredentialType.UNAUTHORIZED or self.runtime.credentials is None:
            return [
                ParameterOption(
                    value="NoOptions",
                    label=I18nObject(en_US="No Options"),
                    icon=None,
                ),
            ]
        # 2. through the subscription properties for all kinds of plugins, auto created and manually created
        # in the case of auto created, create_subscription will save the token to the properties
        access_token = self.runtime.subscription.properties.get("access_tokens")
        if not access_token:
            return [
                ParameterOption(
                    value="NoOptions",
                    label=I18nObject(en_US="No Options"),
                    icon=None,
                ),
            ]
        return [
            ParameterOption(
                value="test",
                label=I18nObject(en_US="test"),
                icon="https://avatars.githubusercontent.com/u/29746822?v=4",
            ),
            ParameterOption(
                value="test2",
                label=I18nObject(en_US="test"),
                icon="https://avatars.githubusercontent.com/u/29746822?v=4",
            ),
            ParameterOption(
                value="test3",
                label=I18nObject(en_US="test"),
                icon="https://avatars.githubusercontent.com/u/29746822?v=4",
            ),
        ]
