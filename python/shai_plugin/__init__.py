from gevent import monkey

# patch all the blocking calls
monkey.patch_all(sys=True)

from shai_plugin.config.config import ShaiPluginEnv
from shai_plugin.interfaces.agent import AgentProvider, AgentStrategy
from shai_plugin.interfaces.endpoint import Endpoint
from shai_plugin.interfaces.model import ModelProvider
from shai_plugin.interfaces.model.large_language_model import LargeLanguageModel
from shai_plugin.interfaces.model.moderation_model import ModerationModel
from shai_plugin.interfaces.model.openai_compatible.llm import OAICompatLargeLanguageModel
from shai_plugin.interfaces.model.openai_compatible.provider import OAICompatProvider
from shai_plugin.interfaces.model.openai_compatible.rerank import OAICompatRerankModel
from shai_plugin.interfaces.model.openai_compatible.speech2text import OAICompatSpeech2TextModel
from shai_plugin.interfaces.model.openai_compatible.text_embedding import OAICompatEmbeddingModel
from shai_plugin.interfaces.model.openai_compatible.tts import OAICompatText2SpeechModel
from shai_plugin.interfaces.model.rerank_model import RerankModel
from shai_plugin.interfaces.model.speech2text_model import Speech2TextModel
from shai_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel
from shai_plugin.interfaces.model.tts_model import TTSModel
from shai_plugin.interfaces.tool import Tool, ToolProvider
from shai_plugin.invocations.file import File
from shai_plugin.plugin import Plugin

__all__ = [
    "AgentProvider",
    "AgentStrategy",
    "ShaiPluginEnv",
    "Endpoint",
    "File",
    "LargeLanguageModel",
    "ModelProvider",
    "ModerationModel",
    "OAICompatEmbeddingModel",
    "OAICompatLargeLanguageModel",
    "OAICompatProvider",
    "OAICompatRerankModel",
    "OAICompatSpeech2TextModel",
    "OAICompatText2SpeechModel",
    "Plugin",
    "RerankModel",
    "Speech2TextModel",
    "TTSModel",
    "TextEmbeddingModel",
    "Tool",
    "ToolProvider",
]
