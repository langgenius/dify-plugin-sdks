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


class GithubRepositoryPullsTool(Tool):
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
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
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

            pulls = []
            for pull in response_data:
                body = pull.get("body") or ""
                pull_info = {
                    "number": pull.get("number", 0),
                    "title": pull.get("title", ""),
                    "body": body[:BODY_PREVIEW_LENGTH] + "..."
                    if len(body) > BODY_PREVIEW_LENGTH
                    else body,
                    "state": pull.get("state", ""),
                    "url": pull.get("html_url", ""),
                    "user": pull.get("user", {}).get("login", ""),
                    "assignee": pull.get("assignee", {}).get("login", "")
                    if pull.get("assignee")
                    else "",
                    "labels": [
                        label.get("name", "") for label in pull.get("labels", [])
                    ],
                    "comments": pull.get("comments", 0),
                    "review_comments": pull.get("review_comments", 0),
                    "commits": pull.get("commits", 0),
                    "additions": pull.get("additions", 0),
                    "deletions": pull.get("deletions", 0),
                    "changed_files": pull.get("changed_files", 0),
                    "mergeable": pull.get("mergeable", None),
                    "merged": pull.get("merged", False),
                    "draft": pull.get("draft", False),
                    "head": {
                        "ref": pull.get("head", {}).get("ref", ""),
                        "sha": pull.get("head", {}).get("sha", "")[:7],
                    },
                    "base": {
                        "ref": pull.get("base", {}).get("ref", ""),
                        "sha": pull.get("base", {}).get("sha", "")[:7],
                    },
                    "created_at": _format_github_timestamp(pull.get("created_at", ""))
                    if pull.get("created_at")
                    else "",
                    "updated_at": _format_github_timestamp(pull.get("updated_at", ""))
                    if pull.get("updated_at")
                    else "",
                }
                pulls.append(pull_info)

            if not pulls:
                yield self.create_text_message(
                    f"No {state} pull requests found in {owner}/{repo}"
                )
            else:
                yield self.create_text_message(
                    self.session.model.summary.invoke(
                        text=json.dumps(pulls, ensure_ascii=False),
                        instruction=(
                            "Summarize the GitHub pull requests in a structured format"
                        ),
                    )
                )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
