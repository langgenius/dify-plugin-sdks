from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dify_plugin.core.runtime import Session
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    EventConfiguration,
    TriggerProviderConfiguration,
    TriggerSubscriptionConstructorRuntime,
)
from dify_plugin.interfaces.trigger import Event, EventRuntime, Trigger, TriggerRuntime, TriggerSubscriptionConstructor


@dataclass(slots=True)
class _TriggerProviderEntry:
    """Internal container storing metadata associated with a trigger provider."""

    configuration: TriggerProviderConfiguration
    provider_cls: type[Trigger]
    subscription_constructor_cls: type[TriggerSubscriptionConstructor] | None
    events: dict[str, tuple[EventConfiguration, type[Event]]]


class TriggerProviderRegistration:
    """Helper that allows incremental registration of provider triggers."""

    def __init__(self, entry: _TriggerProviderEntry) -> None:
        self._entry = entry

    def register_trigger(
        self,
        *,
        name: str,
        configuration: EventConfiguration,
        trigger_cls: type[Event],
    ) -> None:
        """Register an event implementation for the provider."""

        if name in self._entry.events:
            raise ValueError(
                f"Event `{name}` is already registered for provider `{self._entry.configuration.identity.name}`"
            )

        self._entry.events[name] = (configuration, trigger_cls)


class TriggerFactory:
    """Registry that produces trigger related runtime instances on demand."""

    def __init__(self) -> None:
        # Provider name -> runtime metadata. Using a dict allows O(1) lookups when
        # resolving provider classes during request handling.
        self._providers: dict[str, _TriggerProviderEntry] = {}

    def register_trigger_provider(
        self,
        *,
        configuration: TriggerProviderConfiguration,
        provider_cls: type[Trigger],
        subscription_constructor_cls: type[TriggerSubscriptionConstructor] | None,
        events: Mapping[str, tuple[EventConfiguration, type[Event]]],
    ) -> TriggerProviderRegistration:
        """Register a trigger provider and its runtime classes."""

        # Each provider can only be registered once to avoid conflicting runtime
        # definitions when multiple plugins try to use the same identifier.
        provider_name = configuration.identity.name
        if provider_name in self._providers:
            raise ValueError(f"Trigger provider `{provider_name}` is already registered")

        entry = _TriggerProviderEntry(
            configuration=configuration,
            provider_cls=provider_cls,
            subscription_constructor_cls=subscription_constructor_cls,
            events={},
        )

        self._providers[provider_name] = entry

        registration = TriggerProviderRegistration(entry)
        # Pre-populate the registry with events that were already discovered
        # during plugin loading. Providers can keep adding more events by
        # calling ``registration.register_trigger`` inside their module level
        # registration hook.
        for name, (event_config, event_cls) in events.items():
            registration.register_trigger(
                name=name,
                configuration=event_config,
                trigger_cls=event_cls,
            )

        return registration

    # ------------------------------------------------------------------
    # Provider factories
    # ------------------------------------------------------------------
    def get_trigger_provider(
        self,
        provider_name: str,
        session: Session,
        credentials: Mapping[str, Any] | None,
        credential_type: CredentialType | None,
    ) -> Trigger:
        """Instantiate the trigger provider implementation for the given provider name."""

        entry = self._get_entry(provider_name)
        return entry.provider_cls(
            runtime=TriggerRuntime(
                session=session,
                credential_type=credential_type or CredentialType.UNAUTHORIZED,
                credentials=credentials,
            )
        )

    def get_provider_cls(self, provider_name: str) -> type[Trigger]:
        return self._get_entry(provider_name).provider_cls

    def has_subscription_constructor(self, provider_name: str) -> bool:
        return self._get_entry(provider_name).subscription_constructor_cls is not None

    def get_subscription_constructor(
        self,
        provider_name: str,
        runtime: TriggerSubscriptionConstructorRuntime,
    ) -> TriggerSubscriptionConstructor:
        """Instantiate the subscription constructor implementation."""

        entry = self._get_entry(provider_name)
        if not entry.subscription_constructor_cls:
            raise ValueError(f"Trigger provider `{provider_name}` does not define a subscription constructor")

        return entry.subscription_constructor_cls(runtime)

    def get_subscription_constructor_cls(self, provider_name: str) -> type[TriggerSubscriptionConstructor] | None:
        return self._get_entry(provider_name).subscription_constructor_cls

    # ------------------------------------------------------------------
    # Event factories
    # ------------------------------------------------------------------

    def get_trigger_event_handler_safely(self, provider_name: str, event: str, runtime: EventRuntime) -> Event | None:
        entry = self._get_entry(provider_name)
        if event not in entry.events:
            return None
        _, event_cls = entry.events[event]
        return event_cls(runtime)

    def get_trigger_event_handler(self, provider_name: str, event: str, runtime: EventRuntime) -> Event:
        """Instantiate an event for the given provider and event name."""

        entry = self._get_entry(provider_name)
        if event not in entry.events:
            raise ValueError(f"Event `{event}` not found in provider `{provider_name}`")

        _, event_cls = entry.events[event]
        return event_cls(runtime)

    def get_trigger_configuration(self, provider_name: str, event: str) -> EventConfiguration | None:
        entry = self._get_entry(provider_name)
        event_entry = entry.events.get(event)
        if event_entry is None:
            return None
        return event_entry[0]

    def iter_events(self, provider_name: str) -> Mapping[str, tuple[EventConfiguration, type[Event]]]:
        """Return a shallow copy of the registered events for inspection."""

        # Returning a copy ensures callers cannot mutate the internal registry
        # inadvertently, while still providing a dictionary-like interface for
        # tooling and API handlers that need to enumerate events.
        return dict(self._get_entry(provider_name).events)

    def get_configuration(self, provider_name: str) -> TriggerProviderConfiguration:
        return self._get_entry(provider_name).configuration

    def _get_entry(self, provider_name: str) -> _TriggerProviderEntry:
        try:
            return self._providers[provider_name]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"Trigger provider `{provider_name}` not found") from exc
