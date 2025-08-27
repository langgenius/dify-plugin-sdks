import pytest

from dify_plugin.interfaces.trigger import TriggerProvider


def test_construct_trigger_provider():
    """
    Test that the TriggerProvider can be constructed without implementing any methods
    """
    provider = TriggerProvider()
    assert provider is not None


def test_oauth_get_authorization_url():
    """
    Test that the TriggerProvider can get the authorization url
    """
    provider = TriggerProvider()
    with pytest.raises(NotImplementedError):
        provider.oauth_get_authorization_url({})
