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


class GithubUserReposTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        username = tool_parameters.get("username", "")
        per_page = tool_parameters.get("per_page", 10)
        sort = tool_parameters.get("sort", "updated")
        direction = tool_parameters.get("direction", "desc")
        repo_type = tool_parameters.get("type", "all")

        credential_type = self.runtime.credential_type

        if not username:
            yield self.create_text_message("Please input username")
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
        params = {
            "per_page": per_page,
            "sort": sort,
            "direction": direction,
            "type": repo_type,
        }

        try:
            response = urllib3_future.request(
                "GET",
                headers=headers,
                url=f"https://api.github.com/users/{username}/repos",
                fields=params,
                timeout=10,
            )
            response_data = response.json()
            if response.status != HTTPStatus.OK:
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            repos = []
            for repo in response_data:
                repo_info = {
                    "id": repo.get("id", 0),
                    "name": repo.get("name", ""),
                    "full_name": repo.get("full_name", ""),
                    "description": repo.get("description", ""),
                    "url": repo.get("html_url", ""),
                    "clone_url": repo.get("clone_url", ""),
                    "ssh_url": repo.get("ssh_url", ""),
                    "language": repo.get("language", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "watchers": repo.get("watchers_count", 0),
                    "open_issues": repo.get("open_issues_count", 0),
                    "size": repo.get("size", 0),
                    "default_branch": repo.get("default_branch", ""),
                    "is_private": repo.get("private", False),
                    "is_fork": repo.get("fork", False),
                    "is_archived": repo.get("archived", False),
                    "license": repo.get("license", {}).get("name", "")
                    if repo.get("license")
                    else "",
                    "created_at": _format_github_timestamp(repo.get("created_at", ""))
                    if repo.get("created_at")
                    else "",
                    "updated_at": _format_github_timestamp(repo.get("updated_at", ""))
                    if repo.get("updated_at")
                    else "",
                    "pushed_at": _format_github_timestamp(repo.get("pushed_at", ""))
                    if repo.get("pushed_at")
                    else "",
                    "topics": repo.get("topics", []),
                }
                repos.append(repo_info)

            if not repos:
                yield self.create_text_message(
                    f"No repositories found for user {username}"
                )
            else:
                yield self.create_text_message(
                    self.session.model.summary.invoke(
                        text=json.dumps(repos, ensure_ascii=False),
                        instruction=(
                            "Summarize the GitHub user repositories "
                            "in a structured format"
                        ),
                    )
                )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
