import pathlib
from http import HTTPStatus
from typing import IO

import httpx2

from dify_plugin.core.utils import http
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeBadRequestError,
)
from dify_plugin.interfaces.model.openai_compatible.common import _CommonOaiApiCompat
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel


class OAICompatSpeech2TextModel(_CommonOaiApiCompat, Speech2TextModel):
    """Model class for OpenAI Compatible Speech to text model."""

    def _invoke(
        self,
        model: str,
        credentials: dict,
        file: IO[bytes],
        user: str | None = None,
    ) -> str:
        """Invoke speech2text model

        :param model: model name
        :param credentials: model credentials
        :param file: audio file
        :param user: unique user id
        :return: text for given audio file

        Returns:
            The return value.

        Raises:
            InvokeBadRequestError: If model invocation fails.
        """
        del user
        headers = {}

        api_key = credentials.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint_url = self._join_endpoint_url(
            credentials.get("endpoint_url", "https://api.openai.com/v1/"),
            "audio/transcriptions",
        )

        payload = {"model": credentials.get("endpoint_model_name", model)}
        filename = getattr(file, "name", None)
        filename = (
            pathlib.Path(filename).name
            if isinstance(filename, str) and not filename.startswith("<")
            else "file"
        )
        with http.client() as client:
            response = client.post(
                endpoint_url,
                headers=http.headers(headers),
                data=payload,
                files={"file": (filename, file.read())},
                timeout=httpx2.Timeout(300, connect=10, write=10),
                follow_redirects=True,
            )

        if response.status_code != HTTPStatus.OK:
            raise InvokeBadRequestError(response.text)
        response_data = response.json()
        return response_data["text"]

    def validate_credentials(self, model: str, credentials: dict) -> None:
        """Validate model credentials

        :param model: model name
        :param credentials: model credentials
        :return:

        Raises:
            CredentialsValidateFailedError: If credentials validation fails.
        """
        try:
            audio_file_path = self._get_demo_file_path()

            with pathlib.Path(audio_file_path).open("rb") as audio_file:
                self._invoke(model, credentials, audio_file)
        except Exception as ex:
            raise CredentialsValidateFailedError(str(ex)) from ex
