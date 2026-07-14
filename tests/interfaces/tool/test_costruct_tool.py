from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage, ToolRuntime
from dify_plugin.interfaces.tool import Tool


def test_construct_tool() -> None:
    """
    Test the constructor of Tool
    NOTE:
    - This test is to ensure that the constructor of Tool is not overridden.
    - And ensure a breaking change will be detected by CI.
    """

    class ToolImpl(Tool):
        def _invoke(
            self, tool_parameters: Mapping
        ) -> Generator[ToolInvokeMessage, None, None]:
            del tool_parameters
            yield self.create_text_message("Hello, world!")

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    tool = ToolImpl(
        runtime=ToolRuntime(credentials={}, user_id="test", session_id="test"),
        session=session,
    )
    assert tool is not None


def test_construct_tool_default_credential_type() -> None:
    """
    Test the constructor of Tool with default credential type
    """

    class ToolImpl(Tool):
        def _invoke(
            self, tool_parameters: Mapping
        ) -> Generator[ToolInvokeMessage, None, None]:
            del tool_parameters
            yield self.create_text_message("Hello, world!")

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    tool = ToolImpl(
        runtime=ToolRuntime(credentials={}, user_id="test", session_id="test"),
        session=session,
    )
    assert tool is not None

    assert tool.runtime.credential_type == CredentialType.API_KEY


def test_fetch_parameter_options() -> None:
    """
    Test that the Tool can fetch the parameter options
    """

    class ToolImpl(Tool):
        def _invoke(
            self, tool_parameters: Mapping
        ) -> Generator[ToolInvokeMessage, None, None]:
            del tool_parameters
            yield self.create_text_message("Hello, world!")

        def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
            del parameter
            return [ParameterOption(value="test", label=I18nObject(en_us="test"))]

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    tool = ToolImpl(
        runtime=ToolRuntime(credentials={}, user_id="test", session_id="test"),
        session=session,
    )
    assert tool.fetch_parameter_options("test") == [
        ParameterOption(value="test", label=I18nObject(en_us="test"))
    ]


def test_fetch_tree_parameter_options() -> None:
    """
    Test that the Tool can fetch tree parameter options with nested children
    """

    class ToolImpl(Tool):
        def _invoke(
            self, tool_parameters: Mapping
        ) -> Generator[ToolInvokeMessage, None, None]:
            del tool_parameters
            yield self.create_text_message("Hello, world!")

        def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
            del parameter
            return [
                ParameterOption(
                    value="root",
                    label=I18nObject(en_us="Root"),
                    children=[
                        ParameterOption(
                            value="child1", label=I18nObject(en_us="Child 1")
                        ),
                        ParameterOption(
                            value="child2",
                            label=I18nObject(en_us="Child 2"),
                            children=[
                                ParameterOption(
                                    value="grandchild",
                                    label=I18nObject(en_us="Grandchild"),
                                )
                            ],
                        ),
                    ],
                )
            ]

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    tool = ToolImpl(
        runtime=ToolRuntime(credentials={}, user_id="test", session_id="test"),
        session=session,
    )
    options = tool.fetch_parameter_options("test")
    assert len(options) == 1
    assert options[0].value == "root"
    assert options[0].children is not None
    assert len(options[0].children) == 2
    assert options[0].children[1].children is not None
    assert options[0].children[1].children[0].value == "grandchild"
