from collections.abc import Generator

from dify_plugin.entities.datasource import (
    DatasourceMessage,
    OnlineDriveBrowseFilesRequest,
    OnlineDriveBrowseFilesResponse,
    OnlineDriveDownloadFileRequest,
    OnlineDriveFile,
    OnlineDriveFileBucket,
)
from dify_plugin.interfaces.datasource.online_drive import OnlineDriveDatasource


class ContractDrive(OnlineDriveDatasource):
    def _browse_files(
        self, request: OnlineDriveBrowseFilesRequest
    ) -> OnlineDriveBrowseFilesResponse:
        if request.prefix == "empty":
            return OnlineDriveBrowseFilesResponse(result=[])
        last_page = bool(request.next_page_parameters)
        return OnlineDriveBrowseFilesResponse(
            result=[
                OnlineDriveFileBucket(
                    bucket=request.bucket,
                    files=[
                        OnlineDriveFile(
                            id="last-file" if last_page else "file",
                            name="example.txt",
                            size=4,
                            type="file",
                            remote_metadata={"etag": '"v1"'},
                        )
                    ],
                    is_truncated=not last_page,
                    next_page_parameters=None if last_page else {"cursor": "next"},
                )
            ]
        )

    def _download_file(
        self, request: OnlineDriveDownloadFileRequest
    ) -> Generator[DatasourceMessage]:
        self.finished = False
        try:
            yield self.create_blob_message(
                b"data", meta={"mime_type": "text/plain", "file_name": "example.txt"}
            )
            if request.id == "broken":
                msg = "download interrupted"
                raise ValueError(msg)
        finally:
            self.finished = True
