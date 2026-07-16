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


class GithubRepositoryCommitsTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        owner = tool_parameters.get("owner", "")
        repo = tool_parameters.get("repo", "")
        per_page = tool_parameters.get("per_page", 10)
        sha = tool_parameters.get("sha", "")
        path = tool_parameters.get("path", "")

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
            params = {"per_page": per_page}
            if sha:
                params["sha"] = sha
            if path:
                params["path"] = path

            response = urllib3_future.request(
                "GET",
                headers=headers,
                url=f"https://api.github.com/repos/{owner}/{repo}/commits",
                fields=params,
                timeout=10,
            )
            response_data = response.json()

            if response.status != HTTPStatus.OK:
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            commits = []
            for commit in response_data:
                commit_data = commit.get("commit", {})
                author = commit_data.get("author", {})
                committer = commit_data.get("committer", {})
                verification = commit_data.get("verification", {})
                stats = commit.get("stats") or {}
                commits.append({
                    "sha": commit.get("sha", "")[:7],
                    "full_sha": commit.get("sha", ""),
                    "message": commit_data.get("message", ""),
                    "author": {
                        "name": author.get("name", ""),
                        "email": author.get("email", ""),
                        "date": _format_github_timestamp(author["date"])
                        if author.get("date")
                        else "",
                    },
                    "committer": {
                        "name": committer.get("name", ""),
                        "email": committer.get("email", ""),
                        "date": _format_github_timestamp(committer["date"])
                        if committer.get("date")
                        else "",
                    },
                    "url": commit.get("html_url", ""),
                    "comment_count": commit_data.get("comment_count", 0),
                    "verification": {
                        "verified": verification.get("verified", False),
                        "reason": verification.get("reason", ""),
                    },
                    "stats": {
                        "additions": stats.get("additions", 0),
                        "deletions": stats.get("deletions", 0),
                        "total": stats.get("total", 0),
                    }
                    if stats
                    else {},
                    "files_changed": len(commit.get("files") or []),
                })

            if not commits:
                yield self.create_text_message(f"No commits found in {owner}/{repo}")
                return
            yield self.create_text_message(
                self.session.model.summary.invoke(
                    text=json.dumps(commits, ensure_ascii=False),
                    instruction="Summarize the GitHub commits in a structured format",
                )
            )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
