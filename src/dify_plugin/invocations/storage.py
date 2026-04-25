from binascii import hexlify, unhexlify

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation


class StorageInvocationError(Exception):
    """StorageInvocationError is a custom exception raised
    when an issue occurs during the execution of a storage invocation.
    """

    pass


class StorageInvocation(BackwardsInvocation[dict]):
    def set(self, key: str, val: bytes) -> None:
        """
        set a value into persistence storage.

        :raises:
            StorageInvocationError: If the invocation returns an invalid data.
        """
        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {"opt": "set", "key": key, "value": hexlify(val).decode()},
        ):
            if data["data"] == "ok":
                return

            raise StorageInvocationError(f"unexpected data: {data['data']}")

    def get(self, key: str) -> bytes:
        """get a key from persistence storage.

        :raises:
            NotFoundError: If the caller gets a key that does not exist.
        """

        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {
                "opt": "get",
                "key": key,
            },
        ):
            return unhexlify(data["data"])

        raise StorageInvocationError("no data found")

    def delete(self, key: str) -> None:
        """delete a key from persistence storage.

        :raises:
            StorageInvocationError: If the invocation returns an invalid data.
        """
        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {
                "opt": "del",
                "key": key,
            },
        ):
            if data["data"] == "ok":
                return

            raise StorageInvocationError(f"unexpected data: {data['data']}")

        raise StorageInvocationError("no data found")

    def exist(self, key: str) -> bool:
        """Check for the existence of a key in persistence storage.

        :raises:
            StorageInvocationError: If the invocation does not return any data.
        """
        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {
                "opt": "exist",
                "key": key,
            },
        ):
            return data["data"]

        raise StorageInvocationError("no data found")
