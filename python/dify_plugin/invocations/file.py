from enum import Enum
from typing import Optional

import requests
from pydantic import BaseModel, model_validator

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation


class UploadFileResponse(BaseModel):
    class Type(str, Enum):
        DOCUMENT = "document"
        IMAGE = "image"
        VIDEO = "video"
        AUDIO = "audio"

        @classmethod
        def from_mime_type(cls, mime_type: str):
            if mime_type.startswith("image/"):
                return cls.IMAGE
            if mime_type.startswith("video/"):
                return cls.VIDEO
            if mime_type.startswith("audio/"):
                return cls.AUDIO

            return cls.DOCUMENT

    id: str
    name: str
    size: int
    extension: str
    mime_type: str
    type: Optional[Type] = None
    preview_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def validate_type(cls, d):
        if "type" not in d:
            d["type"] = cls.Type.from_mime_type(d.get("mime_type", ""))
        return d

    def to_app_parameter(self) -> dict:
        return {
            "upload_file_id": self.id,
            "transfer_method": "local_file",
            "type": self.Type.from_mime_type(self.mime_type).value,
        }


class File(BackwardsInvocation[dict]):
    def upload(self, filename: str, content: bytes, mimetype: str) -> UploadFileResponse:
        """
        Upload a file

        :param filename: file name
        :param content: file content
        :param mimetype: file mime type

        :return: file id
        """
        for response in self._backwards_invoke(
            InvokeType.UploadFile,
            dict,
            {
                "filename": filename,
                "mimetype": mimetype,
            },
        ):
            url = response.get("url")
            if not url:
                raise Exception("upload file failed, could not get signed url")

            response = requests.post(url, files={"file": (filename, content, mimetype)})  # noqa: S113
            if response.status_code != 201:
                raise Exception(f"upload file failed, status code: {response.status_code}, response: {response.text}")

            return UploadFileResponse(**response.json())

        raise Exception("upload file failed, empty response from server")
