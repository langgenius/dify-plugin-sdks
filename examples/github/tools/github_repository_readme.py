import base64
from collections.abc import Generator
from http import HTTPStatus
from typing import Any

import urllib3_future

from dify_plugin import Tool
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.errors.model import InvokeError


class GithubRepositoryReadmeTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        owner = tool_parameters.get("owner", "")
        repo = tool_parameters.get("repo", "")
        ref = tool_parameters.get("ref", "")
        dir_path = tool_parameters.get("dir", "")
        credential_type = self.runtime.credential_type
        if not owner:
            yield self.create_text_message("Please input owner")
            return
        if not repo:
            yield self.create_text_message("Please input repo")
            return
        if (
            credential_type == CredentialType.API_KEY
            and "access_tokens" not in self.runtime.credentials
        ):
            yield self.create_text_message("GitHub API Access Tokens is required.")
            return

        if (
            credential_type == CredentialType.OAUTH
            and "access_tokens" not in self.runtime.credentials
        ):
            yield self.create_text_message("GitHub OAuth Access Tokens is required.")
            return

        access_token = self.runtime.credentials.get("access_tokens")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        if dir_path:
            url = f"{url}/{dir_path}"

        try:
            response = urllib3_future.request(
                "GET",
                url,
                fields={"ref": ref} if ref else {},
                headers=headers,
                timeout=10,
            )
            response_data = response.json()
        except Exception as exc:
            msg = f"Request failed: {exc}"
            raise InvokeError(msg) from exc

        try:
            if response.status != HTTPStatus.OK:
                message = response_data.get("message")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            encoding = response_data.get("encoding")
            content = response_data.get("content")

            if encoding != "base64":
                msg = (
                    "Can not get base64 encoded readme, "
                    f"response encoding is {encoding}"
                )
                raise InvokeError(msg)
            if not content:
                msg = "README content is empty"
                raise InvokeError(msg)

            yield self.create_text_message(base64.b64decode(content).decode("utf-8"))
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"Request failed: {exc}"
            raise InvokeError(msg) from exc
