"""
HTTPX SSL Configuration Auto-Patcher

Automatically applies SSL configuration from environment variables to all httpx requests.
Supports SSL verification control, custom CA certificates, and mutual TLS (mTLS).

Usage: Simply import dify_plugin - no code changes needed in httpx usage.
"""

import base64
import os
import ssl
import tempfile
from contextlib import contextmanager
from functools import wraps
from typing import Any

import httpx

from dify_plugin.config.config import DifyPluginEnv

# Cache original methods and config to avoid repeated lookups
_original_client_init = getattr(httpx.Client.__init__, "__wrapped__", httpx.Client.__init__)
_original_async_client_init = getattr(httpx.AsyncClient.__init__, "__wrapped__", httpx.AsyncClient.__init__)
_config = DifyPluginEnv()


def _decode_base64(data: str | None) -> bytes | None:
    """Decode base64 string, return None if empty or invalid."""
    if not data:
        return None
    try:
        return base64.b64decode(data)
    except Exception as e:
        raise ValueError(f"Invalid base64 data: {e}") from e


@contextmanager
def _secure_temp_files(*data_list: bytes):
    """Create temporary files with secure permissions (POSIX only)."""
    files = [tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=True) for _ in data_list]
    try:
        for file, data in zip(files, data_list):
            if os.name == "posix":
                os.chmod(file.name, 0o600)
            file.write(data)
            file.flush()
        yield [f.name for f in files]
    finally:
        for file in files:
            file.close()


def _create_ssl_context(config: DifyPluginEnv | None = None) -> ssl.SSLContext | bool:
    """
    Create SSL context from environment configuration.

    Args:
        config: Optional config override (mainly for testing). Uses module-level _config if None.

    Returns:
        False: SSL verification disabled
        True: Default SSL verification
        SSLContext: Custom SSL configuration
    """
    cfg = config or _config

    if not cfg.HTTP_REQUEST_NODE_SSL_VERIFY:
        return False

    # Decode certificate data
    ca_cert = _decode_base64(cfg.HTTP_REQUEST_NODE_SSL_CERT_DATA)
    client_cert = _decode_base64(cfg.HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA)
    client_key = _decode_base64(cfg.HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA)

    # Use default verification if no custom config
    if not any((ca_cert, client_cert, client_key)):
        return True

    # Build custom SSL context
    ctx = ssl.create_default_context()

    # Load custom CA certificate
    if ca_cert:
        try:
            ctx.load_verify_locations(cadata=ca_cert.decode("utf-8"))
        except UnicodeDecodeError as e:
            raise ValueError(f"CA certificate must be valid UTF-8 PEM format: {e}") from e

    # Load client certificate and key for mTLS
    if client_cert and client_key:
        with _secure_temp_files(client_cert, client_key) as (cert_path, key_path):
            ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

    return ctx


def _patch_init(original_init):
    """Create a patched __init__ that injects SSL configuration."""
    @wraps(original_init)
    def patched_init(self, *args: Any, **kwargs: Any) -> None:
        if "verify" not in kwargs:
            kwargs["verify"] = _create_ssl_context()
        return original_init(self, *args, **kwargs)
    return patched_init


# Apply patches
httpx.Client.__init__ = _patch_init(_original_client_init)
httpx.AsyncClient.__init__ = _patch_init(_original_async_client_init)
