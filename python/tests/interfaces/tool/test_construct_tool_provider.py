import pytest

from dify_plugin.interfaces.tool import ToolProvider


def test_construct_tool_provider():
    """
    Test that the ToolProvider can be constructed without implementing any methods
    """
    provider = ToolProvider()
    assert provider is not None


def test_oauth_get_authorization_url():
    """
    Test that the ToolProvider can get the authorization url
    """
    provider = ToolProvider()
    with pytest.raises(NotImplementedError):
        provider.oauth_get_authorization_url({})
