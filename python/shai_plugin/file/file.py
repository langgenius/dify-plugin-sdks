import httpx
from pydantic import BaseModel

from shai_plugin.file.constants import SHAI_FILE_IDENTITY
from shai_plugin.file.entities import FileType


class File(BaseModel):
    shai_model_identity: str = SHAI_FILE_IDENTITY
    url: str
    mime_type: str | None = None
    filename: str | None = None
    extension: str | None = None
    size: int | None = None
    type: FileType

    _blob: bytes | None = None

    @property
    def blob(self) -> bytes:
        """
        Get the file content as a bytes object.

        If the file content is not loaded yet, it will be loaded from the URL and stored in the `_blob` attribute.

        Raises:
            ValueError: If the URL uses an unsupported protocol (e.g., missing 'http://' or 'https://'),
                        suggesting configuration of the FILES_URL environment variable.
            httpx.HTTPStatusError: If the request to fetch the file fails.
        """
        if self._blob is None:
            try:
                response = httpx.get(self.url)
                response.raise_for_status()
                self._blob = response.content
            except httpx.UnsupportedProtocol as e:
                raise ValueError(
                    f"Invalid file URL '{self.url}': {e}. "
                    "Ensure the `FILES_URL` environment variable is set in your .env file"
                ) from e

        assert self._blob is not None
        return self._blob
