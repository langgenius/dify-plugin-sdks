from dify_plugin.config.config import DifyPluginEnv, InstallMethod


def test_launch():
    """
    Env should works without any parameters and env variables
    """
    env = DifyPluginEnv()

    assert InstallMethod.Local == env.INSTALL_METHOD


def test_launch_local_plugin():
    """
    Env should works without any parameters and env variables
    """
    env = DifyPluginEnv(
        INSTALL_METHOD=InstallMethod.Local,
    )

    assert InstallMethod.Local == env.INSTALL_METHOD


def test_launch_remote_plugin():
    """
    Env should works with remote install url and key
    """
    env = DifyPluginEnv(
        INSTALL_METHOD=InstallMethod.Remote,
        REMOTE_INSTALL_URL="debug.dify.ai:5003",
        REMOTE_INSTALL_KEY="19dcf2f3-2856-4fa4-b32b-9ece9b741977",
    )

    assert InstallMethod.Remote == env.INSTALL_METHOD
    assert env.REMOTE_INSTALL_URL == "debug.dify.ai:5003"
    assert env.REMOTE_INSTALL_KEY == "19dcf2f3-2856-4fa4-b32b-9ece9b741977"


def test_launch_serverless_plugin():
    """
    Env should works with serverless install method
    """
    env = DifyPluginEnv(
        INSTALL_METHOD=InstallMethod.Serverless,
        SERVERLESS_HOST="0.0.0.0",
        SERVERLESS_PORT=8080,
    )

    assert InstallMethod.Serverless == env.INSTALL_METHOD
    assert env.SERVERLESS_HOST == "0.0.0.0"
    assert env.SERVERLESS_PORT == 8080
