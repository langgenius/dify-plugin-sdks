from binascii import hexlify, unhexlify

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation


class StorageInvocation(BackwardsInvocation[dict]):
    def set(self, key: str, val: bytes) -> None:
        """
        set a value into persistence storage.
        """
        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {"opt": "set", "key": key, "value": hexlify(val).decode()},
        ):
            if data["data"] == "ok":
                return

            raise Exception("unexpected data")

        Exception("no data found")

    def get(self, key: str) -> bytes:
        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {
                "opt": "get",
                "key": key,
            },
        ):
            return unhexlify(data["data"])

        raise Exception("no data found")

    def delete(self, key: str) -> None:
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

            raise Exception("unexpected data")

        raise Exception("no data found")
        
    def exist(self, key: str) -> bool:
        for data in self._backwards_invoke(
            InvokeType.Storage,
            dict,
            {
                "opt": "exist",
                "key": key,
            },
        ):
            return data["data"]

        raise Exception("no data found")