import hashlib
import logging
import re
import uuid
from abc import abstractmethod
from collections.abc import Generator

from pydantic import ConfigDict

from dify_plugin.entities.model import ModelPropertyKey, ModelType
from dify_plugin.interfaces.model.ai_model import AIModel

logger = logging.getLogger(__name__)

_MIME_TYPE_BY_AUDIO_TYPE = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "aac": "audio/aac",
    "mp4": "audio/mp4",
}


class TTSModel(AIModel):
    """Model class for ttstext model."""

    model_type: ModelType = ModelType.TTS

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(
        self,
        model: str,
        tenant_id: str,
        credentials: dict,
        content_text: str,
        voice: str,
        user: str | None = None,
    ) -> bytes | Generator[bytes, None, None]:
        """Invoke large language model

        :param model: model name
        :param tenant_id: user tenant id
        :param credentials: model credentials
        :param voice: model timbre
        :param content_text: text content to be translated
        :param streaming: output is streaming
        :param user: unique user id
        :return: translated audio file
        """
        raise NotImplementedError

    def get_tts_model_voices(
        self,
        model: str,
        credentials: dict,
        language: str | None = None,
    ) -> list | None:
        """Get voice for given tts model voices

        :param language: tts language
        :param model: model name
        :param credentials: model credentials
        :return: voices lists

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)

        if model_schema and ModelPropertyKey.VOICES in model_schema.model_properties:
            voices = model_schema.model_properties[ModelPropertyKey.VOICES]
            if language:
                return [
                    {"name": d["name"], "value": d["mode"]}
                    for d in voices
                    if language and language in d.get("language")
                ]
            return [{"name": d["name"], "value": d["mode"]} for d in voices]
        return None

    ############################################################
    #            For plugin implementation use only            #
    ############################################################

    def _get_model_default_voice(
        self,
        model: str,
        credentials: dict,
    ) -> object | None:
        """Get voice for given tts model

        :param model: model name
        :param credentials: model credentials
        :return: voice

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)

        if (
            model_schema
            and ModelPropertyKey.DEFAULT_VOICE in model_schema.model_properties
        ):
            return model_schema.model_properties[ModelPropertyKey.DEFAULT_VOICE]
        return None

    def _get_model_audio_type(self, model: str, credentials: dict) -> str | None:
        """Get audio type for given tts model

        :param model: model name
        :param credentials: model credentials
        :return: voice

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)

        if (
            model_schema
            and ModelPropertyKey.AUDIO_TYPE in model_schema.model_properties
        ):
            return model_schema.model_properties[ModelPropertyKey.AUDIO_TYPE]
        return None

    def _get_model_word_limit(self, model: str, credentials: dict) -> int | None:
        """Get audio type for given tts model
        :return: audio type

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)

        if (
            model_schema
            and ModelPropertyKey.WORD_LIMIT in model_schema.model_properties
        ):
            return model_schema.model_properties[ModelPropertyKey.WORD_LIMIT]
        return None

    def _get_model_workers_limit(self, model: str, credentials: dict) -> int | None:
        """Get audio max workers for given tts model
        :return: audio type

        Returns:
            The return value.
        """
        model_schema = self.get_model_schema(model, credentials)

        if (
            model_schema
            and ModelPropertyKey.MAX_WORKERS in model_schema.model_properties
        ):
            return model_schema.model_properties[ModelPropertyKey.MAX_WORKERS]
        return None

    @staticmethod
    def _split_text_into_sentences(
        org_text: str,
        max_length: int = 2000,
        pattern: str = r"[。.!?]",
    ) -> list[str]:
        if max_length <= 0:
            msg = "max_length must be greater than 0"
            raise ValueError(msg)

        sentence_end = re.compile(pattern)
        start = 0
        result: list[str] = []
        while start < len(org_text):
            window_end = min(start + max_length, len(org_text))
            split_at = window_end
            if window_end < len(org_text):
                for match in sentence_end.finditer(org_text, start, window_end):
                    if match.end() > start:
                        split_at = match.end()
            result.append(org_text[start:split_at])
            start = split_at
        return result

    # Streaming behavior can be improved independently of filename generation.
    @staticmethod
    def _get_file_name(file_content: str) -> str:
        hash_object = hashlib.sha256(file_content.encode())
        hex_digest = hash_object.hexdigest()

        namespace_uuid = uuid.UUID("a5da6ef9-b303-596f-8e88-bf8fa40f4b31")
        unique_uuid = uuid.uuid5(namespace_uuid, hex_digest)
        return str(unique_uuid)

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def get_tts_model_mime_type(
        self,
        model: str,
        credentials: dict,
    ) -> str | None:
        """Get the standard MIME type declared by the model schema."""
        return _MIME_TYPE_BY_AUDIO_TYPE.get(
            self._get_model_audio_type(model, credentials)
        )

    def invoke(
        self,
        model: str,
        tenant_id: str,
        credentials: dict,
        content_text: str,
        voice: str,
        user: str | None = None,
    ) -> bytes | Generator[bytes, None, None]:
        """Invoke large language model

        :param model: model name
        :param tenant_id: user tenant id
        :param credentials: model credentials
        :param voice: model timbre
        :param content_text: text content to be translated
        :param streaming: output is streaming
        :param user: unique user id
        :return: translated audio file

        Returns:
            The return value.
        """
        with self.timing_context():
            try:
                result = self._invoke(
                    model=model,
                    tenant_id=tenant_id,
                    credentials=credentials,
                    user=user,
                    content_text=content_text,
                    voice=voice,
                )
            except Exception as e:
                raise self._transform_invoke_error(e) from e

        if isinstance(result, bytes):
            return result

        def generator() -> Generator[bytes, None, None]:
            with self.timing_context():
                try:
                    yield from result
                except Exception as e:
                    raise self._transform_invoke_error(e) from e

        return generator()
