from urllib.parse import urljoin

import httpx2

from dify_plugin.errors.model import (
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
    InvokeServerUnavailableError,
)


class _CommonOaiApiCompat:
    def _join_endpoint_url(self, endpoint_url: str, path: str) -> str:
        return urljoin(f"{endpoint_url.rstrip('/')}/", path)

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error
        The key is the error type thrown to the caller
        The value is the error type thrown by the model,
        which needs to be converted into a unified error type for the caller.

        :return: Invoke error mapping
        """
        return {
            InvokeBadRequestError: [
                httpx2.InvalidURL,
                httpx2.UnsupportedProtocol,
                httpx2.LocalProtocolError,
                httpx2.HTTPStatusError,
            ],
            InvokeConnectionError: [
                httpx2.TimeoutException,
                httpx2.NetworkError,
                httpx2.ProxyError,
            ],
            InvokeServerUnavailableError: [
                httpx2.RemoteProtocolError,
                httpx2.DecodingError,
            ],
        }
