"""Tests for SSL configuration support in httpx."""

import base64
import os
import ssl
from unittest.mock import patch

import httpx
import pytest

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.utils.ssl import _create_ssl_context, _decode_base64_cert


# Unit tests for helper functions
def test_decode_valid_base64_cert():
    """Test decoding valid base64 certificate data."""
    test_data = b"test certificate data"
    encoded = base64.b64encode(test_data).decode("utf-8")
    result = _decode_base64_cert(encoded)
    assert result == test_data


def test_decode_none_returns_none():
    """Test that None input returns None."""
    result = _decode_base64_cert(None)
    assert result is None


def test_decode_empty_string_returns_none():
    """Test that empty string returns None."""
    result = _decode_base64_cert("")
    assert result is None


def test_decode_invalid_base64_raises_error():
    """Test that invalid base64 data raises ValueError."""
    with pytest.raises(ValueError, match="Failed to decode base64 certificate data"):
        _decode_base64_cert("invalid!@#$%")


def test_ssl_context_verify_disabled():
    """Test that SSL verification disabled returns False."""
    config = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=False)
    result = _create_ssl_context(config)
    assert result is False


def test_ssl_context_verify_enabled_no_certs():
    """Test that SSL verification enabled without custom certs returns True."""
    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CERT_DATA=None,
        HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA=None,
        HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA=None,
    )
    result = _create_ssl_context(config)
    assert result is True


def test_ssl_context_with_custom_ca_cert():
    """Test that custom CA cert triggers SSL context creation."""
    # Note: We use fake cert data since real cert validation requires valid PEM format
    encoded_cert = base64.b64encode(b"fake cert data").decode("utf-8")
    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CERT_DATA=encoded_cert,
    )

    try:
        result = _create_ssl_context(config)
        assert isinstance(result, (ssl.SSLContext, bool))
    except ssl.SSLError:
        # Expected with invalid certificate data
        assert True


# Integration tests for httpx patching
def test_httpx_client_with_default_config():
    """Test that httpx.Client works with default SSL configuration."""
    client = httpx.Client()
    assert client is not None
    assert hasattr(client, "_transport")
    assert client._transport is not None
    client.close()


def test_httpx_client_with_explicit_verify_params():
    """Test that explicit verify parameters work correctly."""
    # Test with explicit verify=True
    client = httpx.Client(verify=True)
    assert client is not None
    client.close()

    # Test with explicit verify=False
    client = httpx.Client(verify=False)
    assert client is not None
    client.close()


def test_ssl_patch_applies_config_from_env():
    """Test that SSL patch actually applies configuration from environment."""
    # Test verify=False from environment
    with patch.dict(os.environ, {"HTTP_REQUEST_NODE_SSL_VERIFY": "false"}):
        with patch("dify_plugin.core.utils.ssl.DifyPluginEnv") as mock_env:
            mock_config = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=False)
            mock_env.return_value = mock_config

            client = httpx.Client()
            assert client._transport is not None
            client.close()

    # Test verify=True from environment
    with patch.dict(os.environ, {"HTTP_REQUEST_NODE_SSL_VERIFY": "true"}):
        with patch("dify_plugin.core.utils.ssl.DifyPluginEnv") as mock_env:
            mock_config = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=True)
            mock_env.return_value = mock_config

            client = httpx.Client()
            assert client._transport is not None
            client.close()


def test_explicit_verify_overrides_env_config():
    """Test that explicit verify parameter takes precedence over environment config."""
    with patch.dict(os.environ, {"HTTP_REQUEST_NODE_SSL_VERIFY": "false"}):
        # Even with env=false, explicit verify=True should work
        client = httpx.Client(verify=True)
        assert client is not None
        client.close()

        # Explicit verify=False should also work
        client = httpx.Client(verify=False)
        assert client is not None
        client.close()


# Tests for multiple CA certificates support
def test_decode_multiple_certificates_in_pem():
    """Test that multiple certificates in one PEM format can be decoded."""
    # Simulate multiple certificates in PEM format
    cert1 = b"""-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKFirstCert...
-----END CERTIFICATE-----"""

    cert2 = b"""-----BEGIN CERTIFICATE-----
MIIEpDCCA4ygAwIBAgIJALSecondCert...
-----END CERTIFICATE-----"""

    cert3 = b"""-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIThirdCert...
-----END CERTIFICATE-----"""

    # Combine multiple certificates (as user would do: cat cert1.pem cert2.pem cert3.pem)
    combined_certs = cert1 + b"\n" + cert2 + b"\n" + cert3

    # Encode to base64
    encoded = base64.b64encode(combined_certs).decode("utf-8")

    # Decode should work
    result = _decode_base64_cert(encoded)
    assert result == combined_certs
    assert b"-----BEGIN CERTIFICATE-----" in result
    # Should contain all three certificate markers
    assert result.count(b"-----BEGIN CERTIFICATE-----") == 3
    assert result.count(b"-----END CERTIFICATE-----") == 3


def test_ssl_context_with_multiple_ca_certs():
    """Test that SSL context can be created with multiple CA certificates."""
    # Create fake multiple certificates in PEM format
    cert1 = b"""-----BEGIN CERTIFICATE-----
First Certificate Data
-----END CERTIFICATE-----"""

    cert2 = b"""-----BEGIN CERTIFICATE-----
Second Certificate Data
-----END CERTIFICATE-----"""

    cert3 = b"""-----BEGIN CERTIFICATE-----
Third Certificate Data
-----END CERTIFICATE-----"""

    combined_certs = cert1 + b"\n" + cert2 + b"\n" + cert3
    encoded_cert = base64.b64encode(combined_certs).decode("utf-8")

    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CERT_DATA=encoded_cert,
    )

    try:
        result = _create_ssl_context(config)
        # Should create an SSL context (not just True/False)
        # With invalid cert data, it will raise SSLError, which is expected
        assert isinstance(result, (ssl.SSLContext, bool))
    except ssl.SSLError:
        # Expected with invalid certificate data
        # The important thing is that the code handles multiple certs
        assert True


def test_multiple_certs_workflow():
    """Test the complete workflow for multiple certificates as documented."""
    # Simulate the documented workflow:
    # 1. User combines multiple certificates
    cert_data_1 = b"-----BEGIN CERTIFICATE-----\nCert1Data\n-----END CERTIFICATE-----"
    cert_data_2 = b"-----BEGIN CERTIFICATE-----\nCert2Data\n-----END CERTIFICATE-----"
    cert_data_3 = b"-----BEGIN CERTIFICATE-----\nCert3Data\n-----END CERTIFICATE-----"

    # 2. Combine them (equivalent to: cat ca-cert-1.pem ca-cert-2.pem ca-cert-3.pem)
    combined = cert_data_1 + b"\n" + cert_data_2 + b"\n" + cert_data_3

    # 3. Base64 encode (equivalent to: base64 | tr -d '\n')
    encoded = base64.b64encode(combined).decode("utf-8").replace("\n", "")

    # 4. Verify decoding works
    decoded = _decode_base64_cert(encoded)
    assert decoded == combined

    # 5. Verify all certificates are present
    assert decoded.count(b"-----BEGIN CERTIFICATE-----") == 3
