from enum import StrEnum


class FileType(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    CUSTOM = "custom"

    @staticmethod
    def value_of(value: str) -> "FileType":
        for member in FileType:
            if member.value == value:
                return member
        msg = f"No such file type: {value}"
        raise ValueError(msg)
