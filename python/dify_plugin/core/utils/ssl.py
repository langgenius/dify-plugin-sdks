"""
HTTPX client utility with SSL configuration support.

This module patches httpx.Client.__init__ and httpx.AsyncClient.__init__ to automatically
apply SSL configuration from environment variables. It supports:
- SSL verification control
- Custom CA certificates
- Mutual TLS (mTLS) with client certificates and keys

The patching is done via monkey patching both Client and AsyncClient __init__ methods,
which covers all use cases:
- Direct Client/AsyncClient instantiation: httpx.Client(), httpx.AsyncClient()
- Convenience methods: httpx.get(), httpx.post(), etc. (they internally use Client)

No code changes are needed in places that use httpx.
"""

import base64
import binascii
import os
import ssl
import tempfile
from functools import wraps
from typing import Any

import httpx

from dify_plugin.config.config import DifyPluginEnv

# Store original methods before patching - use getattr to avoid reload issues
_original_client_init = getattr(httpx.Client.__init__, "__wrapped__", httpx.Client.__init__)
_original_async_client_init = getattr(httpx.AsyncClient.__init__, "__wrapped__", httpx.AsyncClient.__init__)

# Instantiate DifyPluginEnv at module level to avoid repeated instantiation
# These environment-based settings are not expected to change during runtime
dify_plugin_env = DifyPluginEnv()


def _decode_base64_cert(data: str | None) -> bytes | None:
    """
    Decode base64 encoded certificate data.

    :param data: Base64 encoded certificate data
    :return: Decoded bytes or None if data is None/empty
    """
    if not data:
        return None
    try:
        return base64.b64decode(data)
    except binascii.Error as e:
        raise ValueError(f"Failed to decode base64 certificate data: {e}") from e


def _create_ssl_context(config: DifyPluginEnv) -> ssl.SSLContext | bool:
    """
    Create SSL context based on environment configuration.

    :param config: DifyPluginEnv configuration instance
    :return: SSL context, True (verify), or False (no verify)
    """
    # If SSL verification is disabled, return False
    if not config.HTTP_REQUEST_NODE_SSL_VERIFY:
        return False

    # Decode all certificate data upfront
    ca_cert_data = _decode_base64_cert(config.HTTP_REQUEST_NODE_SSL_CERT_DATA)
    client_cert_data = _decode_base64_cert(config.HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA)
    client_key_data = _decode_base64_cert(config.HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA)

    # If no custom SSL configuration, use default verification
    if not any((ca_cert_data, client_cert_data, client_key_data)):
        return True

    # Create custom SSL context
    ssl_context = ssl.create_default_context()

    # Load custom CA certificate if provided
    if ca_cert_data:
        # Load CA cert data directly from memory to avoid writing to a temporary file.
        try:
            ca_cert_str = ca_cert_data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Failed to decode CA certificate data as UTF-8. "
                f"Ensure HTTP_REQUEST_NODE_SSL_CERT_DATA contains valid PEM-encoded certificate: {e}"
            ) from e
        ssl_context.load_verify_locations(cadata=ca_cert_str)

    # Load client certificate and key for mutual TLS if provided
    if client_cert_data and client_key_data:
        # Write client cert and key to temporary files with secure permissions
        # Security: Use delete=True (default) so files are automatically deleted when the with block exits
        # ssl.SSLContext.load_cert_chain() reads the file contents into memory, so the files can be deleted immediately after
        with (
            tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=True) as cert_file,
            tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=True) as key_file,
        ):
            # Set restrictive permissions immediately (owner read/write only)
            # This minimizes the risk window while the files exist
            # Only set permissions on POSIX systems (Unix-like), as chmod doesn't work the same way on Windows
            for file, data in [(cert_file, client_cert_data), (key_file, client_key_data)]:
                if os.name == "posix":
                    os.chmod(file.name, 0o600)
                file.write(data)
                file.flush()  # Ensure data is written to disk

            # Load the certificate chain while files still exist
            # load_cert_chain() reads the contents into memory
            ssl_context.load_cert_chain(certfile=cert_file.name, keyfile=key_file.name)

            # Files are automatically deleted when exiting this with block

    return ssl_context


@wraps(_original_client_init)
def _patched_client_init(self, *args: Any, **kwargs: Any) -> None:
    """
    Patched httpx.Client.__init__ that injects SSL configuration.

    This patch covers synchronous httpx usage patterns:
    - httpx.Client() - direct instantiation
    - httpx.get(), httpx.post(), etc. - these internally create Client instances
    """
    if "verify" not in kwargs:
        kwargs["verify"] = _create_ssl_context(dify_plugin_env)
    return _original_client_init(self, *args, **kwargs)


@wraps(_original_async_client_init)
def _patched_async_client_init(self, *args: Any, **kwargs: Any) -> None:
    """
    Patched httpx.AsyncClient.__init__ that injects SSL configuration.

    This patch covers asynchronous httpx usage patterns:
    - httpx.AsyncClient() - direct instantiation
    - Ensures async HTTP requests also use configured SSL settings
    """
    if "verify" not in kwargs:
        kwargs["verify"] = _create_ssl_context(dify_plugin_env)
    return _original_async_client_init(self, *args, **kwargs)


# Apply monkey patches to both Client and AsyncClient
# Both patches are necessary because:
# - httpx.Client handles synchronous requests (httpx.get(), httpx.post(), etc.)
# - httpx.AsyncClient handles asynchronous requests (used in async/await contexts)
# - This project uses gevent, so AsyncClient may be used for async operations
# - Without patching both, async requests would bypass SSL configuration
httpx.Client.__init__ = _patched_client_init
httpx.AsyncClient.__init__ = _patched_async_client_init
