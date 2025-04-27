from dify_plugin.interfaces.tool import ToolProvider


def test_construct_tool_provider():
    """
    Test that the ToolProvider can be constructed without implementing any methods
    """
    provider = ToolProvider()
    assert provider is not None
