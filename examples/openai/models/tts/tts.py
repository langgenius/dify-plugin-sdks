from collections.abc import Generator
from contextlib import closing

from openai import OpenAI

from dify_plugin import TTSModel
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeBadRequestError,
)

from ..common_openai import _CommonOpenAI


class OpenAIText2SpeechModel(_CommonOpenAI, TTSModel):
    """Model class for OpenAI Speech to text model."""

    def _invoke(
        self,
        model: str,
        tenant_id: str,
        credentials: dict,
        content_text: str,
        voice: str,
        user: str | None = None,
    ) -> bytes | Generator[bytes, None, None]:
        """_invoke text2speech model

        :param model: model name
        :param tenant_id: user tenant id
        :param credentials: model credentials
        :param content_text: text content to be translated
        :param voice: model timbre
        :param user: unique user id
        :return: text translated to audio file

        Returns:
            The return value.

        Raises:
            InvokeBadRequestError: If model invocation fails.
        """
        del tenant_id
        del user
        voices = self.get_tts_model_voices(model=model, credentials=credentials)
        if not voices:
            msg = "No voices found for the model"
            raise InvokeBadRequestError(msg)

        if not voice or voice not in [d["value"] for d in voices]:
            voice = self._get_model_default_voice(model, credentials)

        # if streaming:
        return self._tts_invoke_streaming(
            model=model,
            credentials=credentials,
            content_text=content_text,
            voice=voice,
        )

    def validate_credentials(
        self,
        model: str,
        credentials: dict,
        user: str | None = None,
    ) -> None:
        """Validate credentials text2speech model

        :param model: model name
        :param credentials: model credentials
        :param user: unique user id
        :return: text translated to audio file

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
        """
        del user
        try:
            audio = self._tts_invoke_streaming(
                model=model,
                credentials=credentials,
                content_text="Hello Dify!",
                voice=self._get_model_default_voice(model, credentials),
            )
            with closing(audio):
                audio_chunk = next(audio, None)
        except Exception as ex:
            raise CredentialsValidateFailedError(str(ex)) from ex
        if audio_chunk is None:
            msg = "No audio bytes found"
            raise CredentialsValidateFailedError(msg)

    def _tts_invoke_streaming(
        self,
        model: str,
        credentials: dict,
        content_text: str,
        voice: str,
    ) -> Generator[bytes, None, None]:
        """_tts_invoke_streaming text2speech model

        :param model: model name
        :param credentials: model credentials
        :param content_text: text content to be translated
        :param voice: model timbre
        :return: text translated to audio file

        Yields:
            Generated values.

        Raises:
            InvokeBadRequestError: If model invocation fails.
        """
        try:
            client = OpenAI(**self._to_credential_kwargs(credentials))
            word_limit = self._get_model_word_limit(model, credentials) or 500
            sentences = [content_text.strip()]
            if len(content_text) > word_limit:
                sentences = self._split_text_into_sentences(
                    content_text,
                    max_length=word_limit,
                )

            for sentence in sentences:
                with client.audio.speech.with_streaming_response.create(
                    model=model,
                    response_format="mp3",
                    input=sentence,
                    voice=voice,
                ) as stream:
                    yield from stream.iter_bytes(1024)
        except Exception as ex:
            raise InvokeBadRequestError(str(ex)) from ex
