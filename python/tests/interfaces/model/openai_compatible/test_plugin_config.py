"""
Tests for _plugin_config configuration object in openai_compatible/llm.py

These tests verify:
1. Configuration object is properly instantiated at module level
2. Configuration object is a singleton (only one instance at module level)
3. Configuration object has correct default values
4. Configuration object has correct types
"""

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.interfaces.model.openai_compatible import llm


def test_plugin_config_exists():
    """Test that _plugin_config object exists"""
    assert hasattr(llm, "_plugin_config")
    assert llm._plugin_config is not None


def test_plugin_config_type():
    """Test that _plugin_config is an instance of DifyPluginEnv"""
    assert isinstance(llm._plugin_config, DifyPluginEnv)


def test_plugin_config_has_max_request_timeout():
    """Test that _plugin_config has MAX_REQUEST_TIMEOUT attribute"""
    assert hasattr(llm._plugin_config, "MAX_REQUEST_TIMEOUT")
    assert isinstance(llm._plugin_config.MAX_REQUEST_TIMEOUT, int)
    # Default value should be 300 seconds (unless overridden by environment variable)
    assert llm._plugin_config.MAX_REQUEST_TIMEOUT > 0


def test_plugin_config_has_max_invocation_timeout():
    """Test that _plugin_config has MAX_INVOCATION_TIMEOUT attribute"""
    assert hasattr(llm._plugin_config, "MAX_INVOCATION_TIMEOUT")
    assert isinstance(llm._plugin_config.MAX_INVOCATION_TIMEOUT, int)
    # Default value should be 250 seconds (unless overridden by environment variable)
    assert llm._plugin_config.MAX_INVOCATION_TIMEOUT > 0


def test_plugin_config_singleton():
    """Test that configuration object is instantiated only once at module level"""
    # Get the id of the config object
    config_id_1 = id(llm._plugin_config)

    # Import again, should be the same object
    from dify_plugin.interfaces.model.openai_compatible import llm as llm2

    config_id_2 = id(llm2._plugin_config)

    # Verify it's the same object
    assert config_id_1 == config_id_2


def test_plugin_config_timeout_values_reasonable():
    """Test that timeout configuration values are within reasonable range"""
    # MAX_REQUEST_TIMEOUT should be between 1 and 3600 seconds
    assert 1 <= llm._plugin_config.MAX_REQUEST_TIMEOUT <= 3600

    # MAX_INVOCATION_TIMEOUT should be between 1 and 3600 seconds
    assert 1 <= llm._plugin_config.MAX_INVOCATION_TIMEOUT <= 3600


def test_plugin_config_can_create_new_instance():
    """Test that new DifyPluginEnv instances can be created (verify the config class itself works)"""
    new_config = DifyPluginEnv()
    assert isinstance(new_config, DifyPluginEnv)
    assert hasattr(new_config, "MAX_REQUEST_TIMEOUT")
    assert hasattr(new_config, "MAX_INVOCATION_TIMEOUT")
