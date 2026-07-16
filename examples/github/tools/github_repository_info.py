import json
from collections.abc import Generator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import urllib3_future

from dify_plugin import Tool
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.errors.model import InvokeError

GITHUB_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DISPLAY_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_github_timestamp(value: str) -> str:
    parsed = datetime.strptime(value, GITHUB_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    return parsed.strftime(DISPLAY_DATETIME_FORMAT)


class GithubRepositoryInfoTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        owner = tool_parameters.get("owner", "")
        repo = tool_parameters.get("repo", "")
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
        try:
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            url = f"https://api.github.com/repos/{owner}/{repo}"

            response = urllib3_future.request("GET", url, headers=headers, timeout=10)
            response_data = response.json()

            if response.status != HTTPStatus.OK:
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            license_info = response_data.get("license") or {}
            owner_info = response_data.get("owner", {})
            repo_info = {
                "name": response_data.get("name", ""),
                "full_name": response_data.get("full_name", ""),
                "description": response_data.get("description", ""),
                "url": response_data.get("html_url", ""),
                "clone_url": response_data.get("clone_url", ""),
                "ssh_url": response_data.get("ssh_url", ""),
                "language": response_data.get("language", ""),
                "stars": response_data.get("stargazers_count", 0),
                "forks": response_data.get("forks_count", 0),
                "watchers": response_data.get("watchers_count", 0),
                "open_issues": response_data.get("open_issues_count", 0),
                "size": response_data.get("size", 0),
                "default_branch": response_data.get("default_branch", ""),
                "is_private": response_data.get("private", False),
                "is_fork": response_data.get("fork", False),
                "is_archived": response_data.get("archived", False),
                "license": license_info.get("name", ""),
                "created_at": _format_github_timestamp(response_data["created_at"])
                if response_data.get("created_at")
                else "",
                "updated_at": _format_github_timestamp(response_data["updated_at"])
                if response_data.get("updated_at")
                else "",
                "pushed_at": _format_github_timestamp(response_data["pushed_at"])
                if response_data.get("pushed_at")
                else "",
                "topics": response_data.get("topics", []),
                "owner": {
                    "login": owner_info.get("login", ""),
                    "type": owner_info.get("type", ""),
                    "url": owner_info.get("html_url", ""),
                },
            }
            yield self.create_text_message(
                self.session.model.summary.invoke(
                    text=json.dumps(repo_info, ensure_ascii=False),
                    instruction=(
                        "Summarize the repository information in a structured format"
                    ),
                )
            )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
