import decimal
import socket
import time
from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import final

import gevent.socket
from pydantic import ConfigDict

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    PARAMETER_RULE_TEMPLATE,
    AIModelEntity,
    DefaultParameterName,
    ModelType,
    PriceConfig,
    PriceInfo,
    PriceType,
)
from dify_plugin.errors.model import InvokeAuthorizationError, InvokeError
from dify_plugin.interfaces.exec.ai_model import TimingContextRaceConditionError

if socket.socket is gevent.socket.socket:
    import gevent.threadpool

    threadpool = gevent.threadpool.ThreadPool(1)

TOKEN_ESTIMATION_TEXT_LIMIT = 100_000


class AIModel(ABC):
    """
    Base class for all models.

    WARNING: AIModel is not thread-safe, DO NOT use it in multi-threaded environment.
    """

    model_type: ModelType
    model_schemas: list[AIModelEntity]
    started_at: float

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    @final
    def __init__(self, model_schemas: list[AIModelEntity]) -> None:
        """
        Initialize the model

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        # NOTE: started_at is not a class variable, it bound to specific instance
        # FIXES for the issue: https://github.com/dify-ai/dify-plugin-sdk/issues/190
        self.started_at = 0
        self.model_schemas = [
            model_schema
            for model_schema in model_schemas
            if model_schema.model_type == self.model_type
        ]

    @contextmanager
    def timing_context(self) -> Generator[None, None, None]:
        """
        Context manager for timing requests
        """
        if self.started_at:
            msg = (
                "Timing context has been started, DO NOT start it in "
                "multi-threaded environment."
            )
            raise TimingContextRaceConditionError(msg)

        # initialize started_at
        # NOTE: started_at is not a class variable, it bound to specific instance
        # FIXES for the issue: https://github.com/dify-ai/dify-plugin-sdk/issues/190
        self.started_at = time.perf_counter()
        try:
            yield
        finally:
            self.started_at = 0

    @abstractmethod
    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        """
        Validate model credentials

        :param model: model name
        :param credentials: model credentials
        :return:
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error
        The key is the error type thrown to the caller
        The value is the error type thrown by the model,
        which needs to be converted into a unified error type for the caller.

        :return: Invoke error mapping
        """
        raise NotImplementedError

    def _transform_invoke_error(self, error: Exception) -> InvokeError:
        """
        Transform invoke error to unified error

        :param error: model invoke error
        :return: unified error

        Returns:
            The return value.
        """
        provider_name = self.__class__.__module__.split(".")[-3]

        for invoke_error, model_errors in self._invoke_error_mapping.items():
            if isinstance(error, tuple(model_errors)):
                if invoke_error == InvokeAuthorizationError:
                    return invoke_error(
                        description=(
                            f"[{provider_name}] Incorrect model credentials provided, "
                            "please check and try again. "
                        )
                    )

                return invoke_error(
                    description=(
                        f"[{provider_name}] {invoke_error.description}, {error!s}"
                    )
                )

        return InvokeError(description=f"[{provider_name}] Error: {error!s}")

    def get_price(
        self, model: str, credentials: dict, price_type: PriceType, tokens: int
    ) -> PriceInfo:
        """
        Get price for given model and tokens

        :param model: model name
        :param credentials: model credentials
        :param price_type: price type
        :param tokens: number of tokens
        :return: price info

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        # get model schema
        model_schema = self.get_model_schema(model, credentials)

        # get price info from predefined model schema
        price_config: PriceConfig | None = None
        if model_schema and model_schema.pricing:
            price_config = model_schema.pricing

        # get unit price
        unit_price = None
        if price_config:
            if price_type == PriceType.INPUT:
                unit_price = price_config.input
            elif price_type == PriceType.OUTPUT and price_config.output is not None:
                unit_price = price_config.output

        if unit_price is None:
            return PriceInfo(
                unit_price=decimal.Decimal("0.0"),
                unit=decimal.Decimal("0.0"),
                total_amount=decimal.Decimal("0.0"),
                currency="USD",
            )

        # calculate total amount
        if not price_config:
            msg = f"Price config not found for model {model}"
            raise ValueError(msg)
        total_amount = tokens * unit_price * price_config.unit
        total_amount = total_amount.quantize(
            decimal.Decimal("0.0000001"), rounding=decimal.ROUND_HALF_UP
        )

        return PriceInfo(
            unit_price=unit_price,
            unit=price_config.unit,
            total_amount=total_amount,
            currency=price_config.currency,
        )

    def predefined_models(self) -> list[AIModelEntity]:
        """
        Get all predefined models for given provider.

        :return:

        Returns:
            The return value.
        """
        return self.model_schemas

    def get_model_schema(
        self, model: str, credentials: Mapping | None = None
    ) -> AIModelEntity | None:
        """
        Get model schema by model name and credentials

        :param model: model name
        :param credentials: model credentials
        :return: model schema

        Returns:
            The return value.
        """
        # get predefined models (predefined_models)
        models = self.predefined_models()

        model_map = {model.model: model for model in models}
        if model in model_map:
            return model_map[model]

        if credentials:
            model_schema = self.get_customizable_model_schema_from_credentials(
                model, credentials
            )
            if model_schema:
                return model_schema

        return None

    def get_customizable_model_schema_from_credentials(
        self, model: str, credentials: Mapping
    ) -> AIModelEntity | None:
        """
        Get customizable model schema from credentials

        :param model: model name
        :param credentials: model credentials
        :return: model schema

        Returns:
            The return value.
        """
        return self._get_customizable_model_schema(model, credentials)

    def _get_customizable_model_schema(
        self, model: str, credentials: Mapping
    ) -> AIModelEntity | None:
        """Get customizable model schema."""
        schema = self.get_customizable_model_schema(model, credentials)
        if not schema:
            return None

        for rule in schema.parameter_rules:
            if not rule.use_template:
                continue
            try:
                template = self._get_default_parameter_rule_variable_map(
                    DefaultParameterName.value_of(rule.use_template)
                )
            except ValueError:
                continue
            for field in ("max", "min", "default", "precision"):
                if getattr(rule, field) is None and field in template:
                    setattr(rule, field, template[field])
            help_template = template.get("help", {})
            if not rule.help and "help" in template:
                rule.help = I18nObject(en_us=help_template["en_US"])
            elif rule.help:
                if not rule.help.en_us and "en_US" in help_template:
                    rule.help.en_us = help_template["en_US"]
                if not rule.help.zh_hans and "zh_Hans" in help_template:
                    rule.help.zh_hans = help_template["zh_Hans"]
        return schema

    def get_customizable_model_schema(
        self, model: str, credentials: Mapping
    ) -> AIModelEntity | None:
        """
        Get customizable model schema

        :param model: model name
        :param credentials: model credentials
        :return: model schema

        Returns:
            The return value.
        """
        del model
        del credentials
        return None

    def _get_default_parameter_rule_variable_map(
        self, name: DefaultParameterName
    ) -> dict:
        """Get the default rule for an overridable parameter template."""
        default_parameter_rule = PARAMETER_RULE_TEMPLATE.get(name)
        if not default_parameter_rule:
            msg = f"Invalid model parameter rule name {name}"
            raise Exception(msg)
        return default_parameter_rule

    def _get_num_tokens_by_gpt2(self, text: str) -> int:
        """
        Get number of tokens for given prompt messages by gpt2
        Some provider models do not provide an interface for obtaining the
        number of tokens.
        Here, the gpt2 tokenizer is used to calculate the number of tokens.
        This method can be executed offline, and the gpt2 tokenizer has been
        cached in the project.

        :param text: plain text of prompt. You need to convert the original
            message to plain text
        :return: number of tokens

        Returns:
            The return value.
        """

        # ENHANCEMENT:
        # to avoid performance issue, do not calculate the number of tokens
        # for too long text
        # only to promise text length is less than TOKEN_ESTIMATION_TEXT_LIMIT
        if len(text) >= TOKEN_ESTIMATION_TEXT_LIMIT:
            return len(text)

        # check if gevent is patched to main thread
        import tiktoken  # noqa: PLC0415

        if socket.socket is gevent.socket.socket:
            # using gevent real thread to avoid blocking main thread
            result = threadpool.spawn(
                lambda: len(tiktoken.encoding_for_model("gpt2").encode(text))
            )
            return result.get(block=True) or 0

        return len(tiktoken.encoding_for_model("gpt2").encode(text))
