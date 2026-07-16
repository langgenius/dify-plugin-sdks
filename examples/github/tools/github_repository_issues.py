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

BODY_PREVIEW_LENGTH = 200
GITHUB_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DISPLAY_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_github_timestamp(value: str) -> str:
    parsed = datetime.strptime(value, GITHUB_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    return parsed.strftime(DISPLAY_DATETIME_FORMAT)


class GithubRepositoryIssuesTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        owner = tool_parameters.get("owner", "")
        repo = tool_parameters.get("repo", "")
        state = tool_parameters.get("state", "open")
        per_page = tool_parameters.get("per_page", 10)
        sort = tool_parameters.get("sort", "created")
        direction = tool_parameters.get("direction", "desc")

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
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": state,
            "per_page": per_page,
            "sort": sort,
            "direction": direction,
        }

        try:
            response = urllib3_future.request(
                "GET",
                headers=headers,
                url=url,
                fields=params,
                timeout=10,
            )
            response_data = response.json()
            if response.status != HTTPStatus.OK:
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            issues = []
            for issue in response_data:
                # Skip pull requests (they also appear in issues API)
                if issue.get("pull_request"):
                    continue

                issue_info = {
                    "number": issue.get("number", 0),
                    "title": issue.get("title", ""),
                    "body": (issue.get("body", "") or "")[:BODY_PREVIEW_LENGTH] + "..."
                    if len(issue.get("body", "") or "") > BODY_PREVIEW_LENGTH
                    else (issue.get("body", "") or ""),
                    "state": issue.get("state", ""),
                    "url": issue.get("html_url", ""),
                    "user": issue.get("user", {}).get("login", ""),
                    "assignee": issue.get("assignee", {}).get("login", "")
                    if issue.get("assignee")
                    else "",
                    "labels": [
                        label.get("name", "") for label in issue.get("labels", [])
                    ],
                    "comments": issue.get("comments", 0),
                    "created_at": _format_github_timestamp(issue.get("created_at", ""))
                    if issue.get("created_at")
                    else "",
                    "updated_at": _format_github_timestamp(issue.get("updated_at", ""))
                    if issue.get("updated_at")
                    else "",
                }
                issues.append(issue_info)

            if not issues:
                yield self.create_text_message(
                    f"No {state} issues found in {owner}/{repo}"
                )
            else:
                yield self.create_text_message(
                    self.session.model.summary.invoke(
                        text=json.dumps(issues, ensure_ascii=False),
                        instruction=(
                            "Summarize the GitHub issues in a structured format"
                        ),
                    )
                )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
