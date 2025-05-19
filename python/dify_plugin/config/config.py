from enum import Enum
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InstallMethod(Enum):
    Local = "local"
    Remote = "remote"
    Serverless = "serverless"


class DifyPluginEnv(BaseSettings):
    MAX_REQUEST_TIMEOUT: int = Field(default=300, description="Maximum request timeout in seconds")
    MAX_WORKER: int = Field(
        default=1000,
        description="Maximum worker count, gevent will be used for async IO"
        "and you dont need to worry about the thread count",
    )
    HEARTBEAT_INTERVAL: float = Field(default=10, description="Heartbeat interval in seconds")
    INSTALL_METHOD: InstallMethod = Field(
        default=InstallMethod.Local,
        description="Installation method, local or network",
    )

    REMOTE_INSTALL_URL: Optional[str] = Field(default=None, description="Remote installation URL")
    REMOTE_INSTALL_HOST: str = Field(default="localhost", description="Remote installation host")
    REMOTE_INSTALL_PORT: int = Field(default=5003, description="Remote installation port")
    REMOTE_INSTALL_KEY: Optional[str] = Field(default=None, description="Remote installation key")

    SERVERLESS_HOST: str = Field(default="0.0.0.0", description="Serverless host")
    SERVERLESS_PORT: int = Field(default=8080, description="Serverless port")
    SERVERLESS_WORKER_CLASS: str = Field(default="gevent", description="Serverless worker class")
    SERVERLESS_WORKER_CONNECTIONS: int = Field(default=1000, description="Serverless worker connections")
    SERVERLESS_WORKERS: int = Field(default=5, description="Serverless workers")
    SERVERLESS_THREADS: int = Field(default=5, description="Serverless threads")

    DIFY_PLUGIN_DAEMON_URL: str = Field(default="http://localhost:5002", description="backwards invocation address")

    model_config = SettingsConfigDict(
        # read from dotenv format config file
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        # ignore extra attributes
        extra="ignore",
    )
