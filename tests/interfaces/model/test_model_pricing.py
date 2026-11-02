from decimal import Decimal
from types import SimpleNamespace

import pytest

from dify_plugin.entities.model import AIModelEntity, ModelType, PriceConfig, PriceType
from tests.interfaces.model.utils import StubLLM


@pytest.fixture
def priced_model() -> StubLLM:
    return StubLLM([
        AIModelEntity(
            model="model",
            model_type=ModelType.LLM,
            model_properties={},
            pricing=PriceConfig(
                input=Decimal("0.15"),
                output=Decimal("0.6"),
                unit=Decimal("0.000001"),
                currency="USD",
            ),
        )
    ])


@pytest.mark.parametrize(
    ("price_type", "tokens", "unit_price", "expected"),
    [
        (PriceType.INPUT, 0, "0.15", "0.0000000"),
        (PriceType.INPUT, 1, "0.15", "0.0000002"),
        (PriceType.INPUT, 17, "0.15", "0.0000026"),
        (PriceType.OUTPUT, 19, "0.6", "0.0000114"),
        (PriceType.OUTPUT, 1_000_000, "0.6", "0.6000000"),
    ],
)
def test_model_price_uses_decimal_and_rounds_half_up(
    priced_model: StubLLM,
    price_type: PriceType,
    tokens: int,
    unit_price: str,
    expected: str,
) -> None:
    price = priced_model.get_price("model", {}, price_type, tokens)

    assert price.unit_price == Decimal(unit_price)
    assert price.unit == Decimal("0.000001")
    assert price.total_amount == Decimal(expected)
    assert price.currency == "USD"


@pytest.mark.parametrize("price_type", [PriceType.INPUT, PriceType.OUTPUT])
def test_unpriced_model_reports_zero_cost(price_type: PriceType) -> None:
    price = StubLLM([]).get_price("missing", {}, price_type, 100)

    assert price.unit_price == price.unit == price.total_amount == Decimal(0)
    assert price.currency == "USD"


def test_missing_output_price_reports_zero_cost(priced_model: StubLLM) -> None:
    assert priced_model.model_schemas[0].pricing is not None
    priced_model.model_schemas[0].pricing.output = None

    price = priced_model.get_price("model", {}, PriceType.OUTPUT, 100)

    assert price.total_amount == Decimal(0)


def test_llm_usage_preserves_each_cost_and_combines_totals(
    priced_model: StubLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = iter([10.0, 12.5])
    clock = SimpleNamespace(perf_counter=lambda: next(timestamps))
    monkeypatch.setattr("dify_plugin.interfaces.model.ai_model.time", clock)
    monkeypatch.setattr("dify_plugin.interfaces.model.large_language_model.time", clock)

    with priced_model.timing_context():
        usage = priced_model._calc_response_usage("model", {}, 17, 19)

    assert usage.prompt_tokens == 17
    assert usage.completion_tokens == 19
    assert usage.total_tokens == 36
    assert usage.prompt_price == Decimal("0.0000026")
    assert usage.completion_price == Decimal("0.0000114")
    assert usage.total_price == Decimal("0.0000140")
    assert usage.prompt_unit_price == Decimal("0.15")
    assert usage.completion_unit_price == Decimal("0.6")
    assert usage.prompt_price_unit == usage.completion_price_unit == Decimal("0.000001")
    assert usage.currency == "USD"
    assert usage.latency == pytest.approx(2.5)
    assert priced_model.started_at == 0
