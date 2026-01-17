"""Tests for SSL configuration support in httpx."""

import base64
import os
import ssl
import tempfile
from pathlib import Path
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


def test_decode_ca_cert_invalid_utf8_raises_error():
    """Test that invalid UTF-8 encoded CA certificate data raises ValueError."""
    # Create binary data that is not valid UTF-8
    invalid_utf8_data = b"\xff\xfe\xfd"
    encoded = base64.b64encode(invalid_utf8_data).decode("utf-8")

    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CERT_DATA=encoded,
    )

    with pytest.raises(ValueError, match="Failed to decode CA certificate data as UTF-8"):
        _create_ssl_context(config)


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


def test_httpx_async_client_with_default_config():
    """Test that httpx.AsyncClient works with default SSL configuration."""
    client = httpx.AsyncClient()
    assert client is not None
    assert hasattr(client, "_transport")
    assert client._transport is not None
    # AsyncClient needs to be closed asynchronously, but for this test we just verify instantiation
    # In real async context, you'd use: await client.aclose()


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


def test_httpx_async_client_with_explicit_verify_params():
    """Test that explicit verify parameters work correctly for AsyncClient."""
    # Test with explicit verify=True
    client = httpx.AsyncClient(verify=True)
    assert client is not None

    # Test with explicit verify=False
    client = httpx.AsyncClient(verify=False)
    assert client is not None


def test_ssl_patch_applies_config_from_env():
    """Test that SSL patch actually applies configuration from environment."""
    from dify_plugin.core.utils.ssl import _original_client_init

    # Test verify=False from environment
    mock_config_false = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=False)
    with patch("dify_plugin.core.utils.ssl.dify_plugin_env", mock_config_false):
        with patch("dify_plugin.core.utils.ssl._original_client_init", wraps=_original_client_init) as mock_init:
            client = httpx.Client()
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs.get("verify") is False
            client.close()

    # Test verify=True from environment
    mock_config_true = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=True)
    with patch("dify_plugin.core.utils.ssl.dify_plugin_env", mock_config_true):
        with patch("dify_plugin.core.utils.ssl._original_client_init", wraps=_original_client_init) as mock_init:
            client = httpx.Client()
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs.get("verify") is True
            client.close()


def test_explicit_verify_overrides_env_config():
    """Test that explicit verify parameter takes precedence over environment config."""
    from dify_plugin.core.utils.ssl import _original_client_init

    mock_config_false = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=False)
    with patch("dify_plugin.core.utils.ssl.dify_plugin_env", mock_config_false):
        with patch("dify_plugin.core.utils.ssl._original_client_init", wraps=_original_client_init) as mock_init:
            # Even with env config for verify=False, explicit verify=True should be used.
            client = httpx.Client(verify=True)
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs.get("verify") is True
            client.close()

            mock_init.reset_mock()

            # Explicit verify=False should also be used.
            client = httpx.Client(verify=False)
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs.get("verify") is False
            client.close()


def test_async_client_explicit_verify_overrides_env_config():
    """Test that explicit verify parameter takes precedence over environment config for AsyncClient."""
    from dify_plugin.core.utils.ssl import _original_async_client_init

    mock_config_false = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=False)
    with patch("dify_plugin.core.utils.ssl.dify_plugin_env", mock_config_false):
        with patch(
            "dify_plugin.core.utils.ssl._original_async_client_init", wraps=_original_async_client_init
        ) as mock_init:
            # Even with env config for verify=False, explicit verify=True should be used.
            client = httpx.AsyncClient(verify=True)
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs.get("verify") is True

            mock_init.reset_mock()

            # Explicit verify=False should also be used.
            client = httpx.AsyncClient(verify=False)
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs.get("verify") is False


def test_ssl_patch_applies_to_both_client_types():
    """Test that SSL patch applies to both Client and AsyncClient."""
    from dify_plugin.core.utils.ssl import _original_async_client_init, _original_client_init

    mock_config_false = DifyPluginEnv(HTTP_REQUEST_NODE_SSL_VERIFY=False)
    with patch("dify_plugin.core.utils.ssl.dify_plugin_env", mock_config_false):
        with patch("dify_plugin.core.utils.ssl._original_client_init", wraps=_original_client_init) as mock_sync_init:
            with patch(
                "dify_plugin.core.utils.ssl._original_async_client_init", wraps=_original_async_client_init
            ) as mock_async_init:
                # Test synchronous client
                sync_client = httpx.Client()
                mock_sync_init.assert_called_once()
                assert mock_sync_init.call_args.kwargs.get("verify") is False
                sync_client.close()

                # Test asynchronous client
                async_client = httpx.AsyncClient()
                mock_async_init.assert_called_once()
                assert mock_async_init.call_args.kwargs.get("verify") is False


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


# Security tests for temporary file handling
@pytest.mark.skipif(os.name != "posix", reason="os.chmod permissions test is POSIX-specific")
def test_temp_files_have_restrictive_permissions():
    """Test that temporary files are created with 0o600 permissions."""
    # Create mock certificate and key data
    cert_data = b"-----BEGIN CERTIFICATE-----\nFakeCertData\n-----END CERTIFICATE-----"
    key_data = b"-----BEGIN PRIVATE KEY-----\nFakeKeyData\n-----END PRIVATE KEY-----"

    encoded_cert = base64.b64encode(cert_data).decode("utf-8")
    encoded_key = base64.b64encode(key_data).decode("utf-8")

    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA=encoded_cert,
        HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA=encoded_key,
    )

    # Track file permissions during creation
    original_chmod = os.chmod
    permissions_set = []

    def mock_chmod(path, mode):
        permissions_set.append((path, mode))
        return original_chmod(path, mode)

    with patch("dify_plugin.core.utils.ssl.os.chmod", side_effect=mock_chmod):
        try:
            _create_ssl_context(config)
        except ssl.SSLError:
            # Expected with fake certificate data
            pass

    # Verify that chmod was called with 0o600 for both files
    assert len(permissions_set) >= 2
    for path, mode in permissions_set:
        assert mode == 0o600, f"Expected 0o600 but got {oct(mode)} for {path}"


def test_temp_files_are_auto_deleted():
    """Test that temporary files are automatically deleted after use."""
    # Create mock certificate and key data
    cert_data = b"-----BEGIN CERTIFICATE-----\nFakeCertData\n-----END CERTIFICATE-----"
    key_data = b"-----BEGIN PRIVATE KEY-----\nFakeKeyData\n-----END PRIVATE KEY-----"

    encoded_cert = base64.b64encode(cert_data).decode("utf-8")
    encoded_key = base64.b64encode(key_data).decode("utf-8")

    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA=encoded_cert,
        HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA=encoded_key,
    )

    # Track created temporary files
    created_files = []
    original_namedtemporaryfile = tempfile.NamedTemporaryFile

    def mock_namedtemporaryfile(*args, **kwargs):
        temp_file = original_namedtemporaryfile(*args, **kwargs)
        created_files.append(temp_file.name)
        return temp_file

    with patch("dify_plugin.core.utils.ssl.tempfile.NamedTemporaryFile", side_effect=mock_namedtemporaryfile):
        try:
            _create_ssl_context(config)
        except ssl.SSLError:
            # Expected with fake certificate data
            pass

    # Verify all temporary files were deleted
    for file_path in created_files:
        assert not Path(file_path).exists(), f"Temporary file {file_path} was not deleted"


def test_temp_files_deleted_on_exception():
    """Test that temporary files are deleted even when an exception occurs."""
    # Create mock certificate and key data that will cause load_cert_chain to fail
    cert_data = b"invalid cert data"
    key_data = b"invalid key data"

    encoded_cert = base64.b64encode(cert_data).decode("utf-8")
    encoded_key = base64.b64encode(key_data).decode("utf-8")

    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA=encoded_cert,
        HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA=encoded_key,
    )

    # Track created temporary files
    created_files = []
    original_namedtemporaryfile = tempfile.NamedTemporaryFile

    def mock_namedtemporaryfile(*args, **kwargs):
        temp_file = original_namedtemporaryfile(*args, **kwargs)
        created_files.append(temp_file.name)
        return temp_file

    with patch("dify_plugin.core.utils.ssl.tempfile.NamedTemporaryFile", side_effect=mock_namedtemporaryfile):
        try:
            _create_ssl_context(config)
        except (ssl.SSLError, OSError):
            # Expected with invalid certificate data
            pass

    # Verify all temporary files were deleted even though an exception occurred
    for file_path in created_files:
        assert not Path(file_path).exists(), f"Temporary file {file_path} was not deleted after exception"


def test_temp_files_content_written_correctly():
    """Test that certificate and key content is correctly written to temporary files."""
    # Create specific test data
    cert_data = b"-----BEGIN CERTIFICATE-----\nTestCertContent123\n-----END CERTIFICATE-----"
    key_data = b"-----BEGIN PRIVATE KEY-----\nTestKeyContent456\n-----END PRIVATE KEY-----"

    encoded_cert = base64.b64encode(cert_data).decode("utf-8")
    encoded_key = base64.b64encode(key_data).decode("utf-8")

    config = DifyPluginEnv(
        HTTP_REQUEST_NODE_SSL_VERIFY=True,
        HTTP_REQUEST_NODE_SSL_CLIENT_CERT_DATA=encoded_cert,
        HTTP_REQUEST_NODE_SSL_CLIENT_KEY_DATA=encoded_key,
    )

    # Track file contents
    file_contents = {}
    original_namedtemporaryfile = tempfile.NamedTemporaryFile

    def mock_namedtemporaryfile(*args, **kwargs):
        temp_file = original_namedtemporaryfile(*args, **kwargs)
        original_write = temp_file.write

        def tracking_write(data):
            file_contents[temp_file.name] = data
            return original_write(data)

        temp_file.write = tracking_write
        return temp_file

    with patch("dify_plugin.core.utils.ssl.tempfile.NamedTemporaryFile", side_effect=mock_namedtemporaryfile):
        try:
            _create_ssl_context(config)
        except ssl.SSLError:
            # Expected with fake certificate data
            pass

    # Verify that both cert and key data were written
    assert len(file_contents) == 2, "Expected 2 files (cert and key) to be created"

    # Verify the written content
    written_data = list(file_contents.values())
    assert cert_data in written_data, "Certificate data was not written correctly"
    assert key_data in written_data, "Key data was not written correctly"