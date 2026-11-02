from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace

import pytest

from dify_plugin.entities.model import ModelType
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.exec.ai_model import TimingContextRaceConditionError
from dify_plugin.interfaces.model.ai_model import AIModel


class MockAIModel(AIModel):
    model_type = ModelType.LLM

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}


def test_ai_model_timing_context_rejects_overlapping_use() -> None:
    model = MockAIModel([])
    entered = Event()
    release = Event()

    def owner() -> float:
        with model.timing_context():
            started_at = model.started_at
            entered.set()
            assert release.wait(timeout=5)
            assert model.started_at == started_at
            return started_at

    def contender() -> None:
        with model.timing_context():
            pytest.fail("An active timing context must reject a second caller")

    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(owner)
        try:
            assert entered.wait(timeout=5)
            rejected = pool.submit(contender)
            with pytest.raises(TimingContextRaceConditionError):
                rejected.result(timeout=5)
        finally:
            release.set()
        assert running.result(timeout=5) > 0

    assert model.started_at == 0


def test_ai_model_timing_context_multiple_sequential_uses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = iter([10.0, 25.0])
    monkeypatch.setattr(
        "dify_plugin.interfaces.model.ai_model.time",
        SimpleNamespace(perf_counter=lambda: next(timestamps)),
    )
    model = MockAIModel([])

    for expected in (10.0, 25.0):
        with model.timing_context():
            assert model.started_at == expected
        assert model.started_at == 0


@pytest.mark.parametrize("error", [RuntimeError("failed"), GeneratorExit()])
def test_ai_model_timing_context_resets_after_error(error: BaseException) -> None:
    model = MockAIModel([])

    with pytest.raises(type(error)) as exc_info, model.timing_context():
        raise error

    assert exc_info.value is error
    assert model.started_at == 0


def test_ai_model_timing_context_is_independent_per_instance() -> None:
    models = [MockAIModel([]) for _ in range(4)]
    rendezvous = Barrier(len(models))

    def invoke(model: MockAIModel) -> float:
        with model.timing_context():
            started_at = model.started_at
            rendezvous.wait(timeout=5)
            assert all(other.started_at > 0 for other in models)
            rendezvous.wait(timeout=5)
            return started_at

    with ThreadPoolExecutor(max_workers=len(models)) as pool:
        starts = list(pool.map(invoke, models))

    assert len(starts) == len(models)
    assert all(start > 0 for start in starts)
    assert all(model.started_at == 0 for model in models)
