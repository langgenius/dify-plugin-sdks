import json
from collections.abc import Generator
from http import HTTPStatus
from typing import Any

import urllib3_future

from dify_plugin import Tool
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.errors.model import InvokeError


class GithubRepositoryContributorsTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        owner = tool_parameters.get("owner", "")
        repo = tool_parameters.get("repo", "")
        per_page = tool_parameters.get("per_page", 10)

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
            response = urllib3_future.request(
                "GET",
                headers=headers,
                url=f"https://api.github.com/repos/{owner}/{repo}/contributors",
                fields={"per_page": per_page},
                timeout=10,
            )
            response_data = response.json()

            if response.status != HTTPStatus.OK:
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            contributors = [
                {
                    "login": contributor.get("login", ""),
                    "id": contributor.get("id", 0),
                    "avatar_url": contributor.get("avatar_url", ""),
                    "url": contributor.get("html_url", ""),
                    "contributions": contributor.get("contributions", 0),
                    "type": contributor.get("type", ""),
                    "site_admin": contributor.get("site_admin", False),
                }
                for contributor in response_data
            ]
            if not contributors:
                yield self.create_text_message(
                    f"No contributors found in {owner}/{repo}"
                )
                return
            yield self.create_text_message(
                self.session.model.summary.invoke(
                    text=json.dumps(contributors, ensure_ascii=False),
                    instruction=(
                        "Summarize the GitHub contributors in a structured format"
                    ),
                )
            )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
