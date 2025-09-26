from __future__ import annotations

"""Utilities for registering trigger providers and retrieving runtime classes."""

from collections.abc import Mapping
from dataclasses import dataclass

from dify_plugin.core.runtime import Session
from dify_plugin.entities.trigger import (
    TriggerConfiguration,
    TriggerProviderConfiguration,
    TriggerSubscriptionConstructorRuntime,
)
from dify_plugin.interfaces.trigger import TriggerEvent, TriggerProvider, TriggerSubscriptionConstructor


@dataclass(slots=True)
class _TriggerProviderEntry:
    """Internal container storing metadata associated with a trigger provider."""

    configuration: TriggerProviderConfiguration
    provider_cls: type[TriggerProvider]
    subscription_constructor_cls: type[TriggerSubscriptionConstructor] | None
    triggers: dict[str, tuple[TriggerConfiguration, type[TriggerEvent]]]


class TriggerProviderRegistration:
    """Helper that allows incremental registration of provider triggers."""

    def __init__(self, entry: _TriggerProviderEntry) -> None:
        self._entry = entry

    def register_trigger(
        self,
        *,
        name: str,
        configuration: TriggerConfiguration,
        trigger_cls: type[TriggerEvent],
    ) -> None:
        """Register a trigger implementation for the provider."""

        if name in self._entry.triggers:
            raise ValueError(
                f"Trigger `{name}` is already registered for provider `{self._entry.configuration.identity.name}`"
            )

        self._entry.triggers[name] = (configuration, trigger_cls)


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
        provider_cls: type[TriggerProvider],
        subscription_constructor_cls: type[TriggerSubscriptionConstructor] | None,
        triggers: Mapping[str, tuple[TriggerConfiguration, type[TriggerEvent]]],
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
            triggers={},
        )

        self._providers[provider_name] = entry

        registration = TriggerProviderRegistration(entry)
        # Pre-populate the registry with triggers that were already discovered
        # during plugin loading. Providers can keep adding more triggers by
        # calling ``registration.register_trigger`` inside their module level
        # registration hook.
        for name, (trigger_config, trigger_cls) in triggers.items():
            registration.register_trigger(
                name=name,
                configuration=trigger_config,
                trigger_cls=trigger_cls,
            )

        return registration

    # ------------------------------------------------------------------
    # Provider factories
    # ------------------------------------------------------------------
    def get_trigger_provider(self, provider_name: str, session: Session) -> TriggerProvider:
        """Instantiate the trigger provider implementation for the given provider name."""

        entry = self._get_entry(provider_name)
        return entry.provider_cls(session)

    def get_provider_cls(self, provider_name: str) -> type[TriggerProvider]:
        return self._get_entry(provider_name).provider_cls

    def has_subscription_constructor(self, provider_name: str) -> bool:
        return self._get_entry(provider_name).subscription_constructor_cls is not None

    def get_subscription_constructor(
        self,
        provider_name: str,
        runtime: TriggerSubscriptionConstructorRuntime,
        session: Session,
    ) -> TriggerSubscriptionConstructor:
        """Instantiate the subscription constructor implementation."""

        entry = self._get_entry(provider_name)
        if not entry.subscription_constructor_cls:
            raise ValueError(f"Trigger provider `{provider_name}` does not define a subscription constructor")

        return entry.subscription_constructor_cls(runtime, session)

    def get_subscription_constructor_cls(
        self, provider_name: str
    ) -> type[TriggerSubscriptionConstructor] | None:
        return self._get_entry(provider_name).subscription_constructor_cls

    # ------------------------------------------------------------------
    # Trigger event factories
    # ------------------------------------------------------------------
    def get_trigger_event_handler(self, provider_name: str, event: str, session: Session) -> TriggerEvent:
        """Instantiate a trigger event handler for the given provider and event name."""

        entry = self._get_entry(provider_name)
        if event not in entry.triggers:
            raise ValueError(f"Trigger `{event}` not found in provider `{provider_name}`")

        _, trigger_cls = entry.triggers[event]
        return trigger_cls(session)

    def get_trigger_configuration(
        self, provider_name: str, event: str
    ) -> TriggerConfiguration | None:
        entry = self._get_entry(provider_name)
        trigger = entry.triggers.get(event)
        if trigger is None:
            return None
        return trigger[0]

    def iter_triggers(self, provider_name: str) -> Mapping[str, tuple[TriggerConfiguration, type[TriggerEvent]]]:
        """Return a shallow copy of the registered triggers for inspection."""

        # Returning a copy ensures callers cannot mutate the internal registry
        # inadvertently, while still providing a dictionary-like interface for
        # tooling and API handlers that need to enumerate triggers.
        return dict(self._get_entry(provider_name).triggers)

    def get_configuration(self, provider_name: str) -> TriggerProviderConfiguration:
        return self._get_entry(provider_name).configuration

    def _get_entry(self, provider_name: str) -> _TriggerProviderEntry:
        try:
            return self._providers[provider_name]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"Trigger provider `{provider_name}` not found") from exc
