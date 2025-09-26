import pytest

from dify_plugin.interfaces.datasource import DatasourceProvider


def test_construct_datasource_provider():
    """
    Test that the DatasourceProvider can be constructed without implementing any methods
    """
    provider = DatasourceProvider()
    assert provider is not None


def test_oauth_get_authorization_url():
    """
    Test that the DatasourceProvider can get the authorization url
    """
    provider = DatasourceProvider()
    with pytest.raises(NotImplementedError):
        provider.oauth_get_authorization_url("", {})
