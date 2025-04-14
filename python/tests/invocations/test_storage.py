from typing import Any, Generator

from dify_plugin.invocations.storage import (
    StorageInvocation,
    StorageInvocationError,
    NotFoundError,
)
from dify_plugin.core.entities.invocation import InvokeType


import pytest


def test_error_hierarchy():
    assert issubclass(StorageInvocationError, Exception)
    assert issubclass(NotFoundError, StorageInvocationError)


class DummyStorageInvocation(StorageInvocation):
    def __init__(self, return_values: list[dict]):
        self._return_values = return_values

    def _backwards_invoke(
        self,
        type: InvokeType,  # noqa: A002
        data_type: Any,
        data: dict,
    ) -> Generator[dict, None, None]:
        _ = type
        _ = data_type
        _ = data
        yield from self._return_values


class TestStorageInvocationExceptionRaises:
    def test_get_should_raise_not_found_error_if_key_not_exist(self):
        storage = DummyStorageInvocation([])
        with pytest.raises(NotFoundError):
            storage.get("test_key")

    def test_set_should_raise_storage_invocation_error_if_data_is_invalid(self):
        storage = DummyStorageInvocation([{"data": "invalid_data"}])
        with pytest.raises(StorageInvocationError):
            storage.set("test_key", b"test_value")

    def test_delete_should_raise_storage_invocation_error_if_data_is_invalid(self):
        storage = DummyStorageInvocation([{"data": "invalid_data"}])
        with pytest.raises(StorageInvocationError):
            storage.delete("test_key")

    def test_delete_should_raise_not_found_error_if_key_not_exist(self):
        storage = DummyStorageInvocation([])
        with pytest.raises(NotFoundError):
            storage.delete("test_key")


class TestSoterageInvocation:
    def test_get_should_return_value(self):
        storage = DummyStorageInvocation([{"data": b"68656c6c6f"}])
        assert storage.get("test_key") == b"hello"

    def test_set_should_set_value(self):
        storage = DummyStorageInvocation([{"data": "ok"}])
        storage.set("test_key", b"test_value")

    def test_delete(self):
        storage = DummyStorageInvocation([{"data": "ok"}])
        storage.delete("test_key")
