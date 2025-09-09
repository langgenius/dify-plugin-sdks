import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

import pytest

from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.exec.ai_model import TimingContextRaceConditionError
from dify_plugin.interfaces.model.ai_model import AIModel


class MockAIModel(AIModel):
    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        """
        Validate model credentials

        :param model: model name
        :param credentials: model credentials
        :return: None
        """
        pass

    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error

        :return: Invoke error mapping
        """
        return {}

    def invoke(self) -> float:
        """
        Invoke model
        """
        with self.timing_context():
            time.sleep(1)
            return time.perf_counter() - self.started_at


def test_ai_model_timing_context_with_race_condition():
    model = MockAIModel(model_schemas=[])

    concurrency = 2

    def task(_):
        """
        Task to be executed in thread pool
        """
        model.invoke()

    with pytest.raises(TimingContextRaceConditionError), ThreadPoolExecutor(concurrency) as pool:
        list(pool.map(task, range(concurrency)))


def test_ai_model_timing_context_multiple_sequential_uses():
    """
    Check if multiple sequential uses of the timing context are correct
    """
    model = MockAIModel(model_schemas=[])

    time_cost = model.invoke()
    assert time_cost > 0
    assert time_cost < 1.5
    time_cost = model.invoke()
    assert time_cost > 0
    assert time_cost < 1.5

    assert model.started_at == 0


def test_ai_model_timing_context_check_latency():
    concurrency = 10

    def task(_):
        """
        Check if race condition is raised
        """
        model = MockAIModel(model_schemas=[])
        time_cost = model.invoke()
        assert time_cost > 0
        assert time_cost < 1.5

    with ThreadPoolExecutor(concurrency) as pool:
        list(pool.map(task, range(concurrency)))
