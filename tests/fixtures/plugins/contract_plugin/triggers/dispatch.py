from triggers.constructor import ContractConstructor
from werkzeug import Request, Response

from dify_plugin.entities.trigger import EventDispatch, Subscription
from dify_plugin.errors.trigger import TriggerValidationError
from dify_plugin.interfaces.trigger import Trigger

__all__ = ["ContractConstructor", "ContractTrigger"]


class ContractTrigger(Trigger):
    def _dispatch_event(
        self, subscription: Subscription, request: Request
    ) -> EventDispatch:
        if subscription.properties.get("reject"):
            msg = "invalid webhook"
            raise TriggerValidationError(msg)
        return EventDispatch(
            user_id=request.get_json().get("sender", ""),
            events=["echo"],
            response=Response("accepted", status=202),
            payload=request.get_json(),
        )
