from binascii import unhexlify
from collections.abc import Generator

from shai_plugin.core.entities.invocation import InvokeType
from shai_plugin.core.runtime import BackwardsInvocation
from shai_plugin.entities.model.tts import TTSModelConfig, TTSResult


class TTSInvocation(BackwardsInvocation[TTSResult]):
    def invoke(self, model_config: TTSModelConfig, content_text: str) -> Generator[bytes, None, None]:
        """
        Invoke tts
        """
        for data in self._backwards_invoke(
            InvokeType.TTS,
            TTSResult,
            {
                **model_config.model_dump(),
                "content_text": content_text,
            },
        ):
            yield unhexlify(data.result)
