from collections.abc import Generator

import pytest

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.invocations.storage import (
    StorageInvocation,
    StorageInvocationError,
)


def test_error_hierarchy() -> None:
    assert issubclass(StorageInvocationError, Exception)


class DummyStorageInvocation(StorageInvocation):
    def __init__(self, return_values: list[dict]) -> None:
        self._return_values = return_values
        self.requests: list[tuple[InvokeType, type[dict], dict]] = []

    def _backwards_invoke(
        self,
        type: InvokeType,  # ruff:ignore[builtin-argument-shadowing]
        data_type: type[dict],
        data: dict,
    ) -> Generator[dict, None, None]:
        self.requests.append((type, data_type, data))
        yield from self._return_values


class TestStorageInvocationExceptionRaises:
    def test_get_should_raise_not_found_error_if_key_not_exist(self) -> None:
        storage = DummyStorageInvocation([])
        with pytest.raises(StorageInvocationError):
            storage.get("test_key")

    def test_set_should_raise_storage_invocation_error_if_data_is_invalid(self) -> None:
        storage = DummyStorageInvocation([{"data": "invalid_data"}])
        with pytest.raises(StorageInvocationError):
            storage.set("test_key", b"test_value")

    def test_delete_should_raise_storage_invocation_error_if_data_is_invalid(
        self,
    ) -> None:
        storage = DummyStorageInvocation([{"data": "invalid_data"}])
        with pytest.raises(StorageInvocationError):
            storage.delete("test_key")

    def test_delete_should_raise_not_found_error_if_key_not_exist(self) -> None:
        storage = DummyStorageInvocation([])
        with pytest.raises(StorageInvocationError):
            storage.delete("test_key")

    def test_exist_should_raise_storage_invocation_error_if_data_is_invalid(
        self,
    ) -> None:
        storage = DummyStorageInvocation([])
        with pytest.raises(StorageInvocationError):
            storage.exist("test_key")


class TestStorageInvocation:
    def test_get_should_return_value(self) -> None:
        storage = DummyStorageInvocation([{"data": b"68656c6c6f"}])
        assert storage.get("test_key") == b"hello"

    def test_set_should_set_value(self) -> None:
        storage = DummyStorageInvocation([{"data": "ok"}])
        storage.set("test_key", b"test_value")

    def test_delete(self) -> None:
        storage = DummyStorageInvocation([{"data": "ok"}])
        storage.delete("test_key")

    def test_exist(self) -> None:
        storage = DummyStorageInvocation([{"data": True}])
        assert storage.exist("test_key")

        storage = DummyStorageInvocation([{"data": False}])
        assert not storage.exist("test_key")


@pytest.mark.parametrize("value", [b"", b"\x00\xff\x80", "你好".encode()])
def test_storage_records_binary_values_and_keys(value: bytes) -> None:
    key = "文件/状态"
    storage = DummyStorageInvocation([{"data": "ok"}])
    storage.set(key, value)
    assert storage.requests == [
        (InvokeType.Storage, dict, {"opt": "set", "key": key, "value": value.hex()})
    ]

    storage = DummyStorageInvocation([{"data": value.hex()}])
    assert storage.get(key) == value
    assert storage.requests == [(InvokeType.Storage, dict, {"opt": "get", "key": key})]


@pytest.mark.parametrize(
    ("method", "operation", "data"),
    [("delete", "del", "ok"), ("exist", "exist", False)],
)
def test_storage_records_operation_and_key(
    method: str, operation: str, data: object
) -> None:
    storage = DummyStorageInvocation([{"data": data}])
    getattr(storage, method)("key")
    assert storage.requests == [
        (InvokeType.Storage, dict, {"opt": operation, "key": "key"})
    ]


def test_set_accepts_an_empty_response() -> None:
    storage = DummyStorageInvocation([])
    assert storage.set("key", b"value") is None
