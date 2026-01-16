"""
HTTPX client utility with SSL configuration support.

This module patches httpx.Client.__init__ to automatically apply SSL configuration
from environment variables. It supports:
- SSL verification control
- Custom CA certificates
- Mutual TLS (mTLS) with client certificates and keys

The patching is done via monkey patching httpx.Client.__init__, which covers all use cases:
- Direct Client instantiation: httpx.Client()
- Convenience methods: httpx.get(), httpx.post(), etc. (they internally use Client)

No code changes are needed in places that use httpx.
"""

import base64
import ssl
import tempfile
from functools import wraps
from pathlib import Path
from typing import Any

import httpx

from dify_plugin.config.config import DifyPluginEnv

# Store original method before patching - use getattr to avoid reload issues
_original_client_init = getattr(httpx.Client.__init__, "__wrapped__", httpx.Client.__init__)


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
    except Exception as e:
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

    # Check if we have custom SSL configuration
    has_ca_cert = bool(config.HTTP_REQUEST_NODE_SSL_CERT_DATA)
    has_client_cert = bool(config.HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA)
    has_client_key = bool(config.HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA)

    # If no custom SSL configuration, use default verification
    if not (has_ca_cert or has_client_cert or has_client_key):
        return True

    # Create custom SSL context
    ssl_context = ssl.create_default_context()

    # Load custom CA certificate if provided
    if has_ca_cert:
        ca_cert_data = _decode_base64_cert(config.HTTP_REQUEST_NODE_SSL_CERT_DATA)
        if ca_cert_data:
            # Load CA cert data directly from memory to avoid writing to a temporary file.
            ssl_context.load_verify_locations(cadata=ca_cert_data.decode("utf-8"))

    # Load client certificate and key for mutual TLS if provided
    if has_client_cert and has_client_key:
        client_cert_data = _decode_base64_cert(config.HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA)
        client_key_data = _decode_base64_cert(config.HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA)

        if client_cert_data and client_key_data:
            # Write client cert and key to temporary files
            with (
                tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=False) as cert_file,
                tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=False) as key_file,
            ):
                cert_file.write(client_cert_data)
                key_file.write(client_key_data)
                cert_path = cert_file.name
                key_path = key_file.name

            try:
                ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            finally:
                # Clean up temporary files
                Path(cert_path).unlink(missing_ok=True)
                Path(key_path).unlink(missing_ok=True)

    return ssl_context


@wraps(_original_client_init)
def _patched_client_init(self, *args: Any, **kwargs: Any) -> None:
    """
    Patched httpx.Client.__init__ that injects SSL configuration.

    This single patch covers all httpx usage patterns:
    - httpx.Client() - direct instantiation
    - httpx.get(), httpx.post(), etc. - these internally create Client instances
    """
    if "verify" not in kwargs:
        config = DifyPluginEnv()
        kwargs["verify"] = _create_ssl_context(config)
    return _original_client_init(self, *args, **kwargs)


# Apply monkey patch to httpx.Client.__init__
# This single patch is sufficient because:
# - httpx.get/post/put/delete/patch/head/options all call httpx.request()
# - httpx.request() creates a Client instance internally with the verify parameter
# - So patching Client.__init__ catches all cases
httpx.Client.__init__ = _patched_client_init
