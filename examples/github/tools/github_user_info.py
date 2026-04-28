import json
from collections.abc import Generator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.errors.model import InvokeError

GITHUB_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DISPLAY_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_github_timestamp(value: str) -> str:
    parsed = datetime.strptime(value, GITHUB_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    return parsed.strftime(DISPLAY_DATETIME_FORMAT)


class GithubUserInfoTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        username = tool_parameters.get("username", "")

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
        try:
            headers = {
                "Content-Type": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            s = requests.session()
            api_domain = "https://api.github.com"
            url = f"{api_domain}/users/{username}"

            response = s.request(
                method="GET",
                headers=headers,
                url=url,
            )

            if response.status_code == HTTPStatus.OK:
                response_data = response.json()

                user_info = {
                    "login": response_data.get("login", ""),
                    "id": response_data.get("id", 0),
                    "name": response_data.get("name", ""),
                    "company": response_data.get("company", ""),
                    "blog": response_data.get("blog", ""),
                    "location": response_data.get("location", ""),
                    "email": response_data.get("email", ""),
                    "bio": response_data.get("bio", ""),
                    "twitter_username": response_data.get("twitter_username", ""),
                    "avatar_url": response_data.get("avatar_url", ""),
                    "url": response_data.get("html_url", ""),
                    "type": response_data.get("type", ""),
                    "site_admin": response_data.get("site_admin", False),
                    "public_repos": response_data.get("public_repos", 0),
                    "public_gists": response_data.get("public_gists", 0),
                    "followers": response_data.get("followers", 0),
                    "following": response_data.get("following", 0),
                    "created_at": _format_github_timestamp(
                        response_data.get("created_at", "")
                    )
                    if response_data.get("created_at")
                    else "",
                    "updated_at": _format_github_timestamp(
                        response_data.get("updated_at", "")
                    )
                    if response_data.get("updated_at")
                    else "",
                    "hireable": response_data.get("hireable", None),
                    "gravatar_id": response_data.get("gravatar_id", ""),
                }

                s.close()

                yield self.create_text_message(
                    self.session.model.summary.invoke(
                        text=json.dumps(user_info, ensure_ascii=False),
                        instruction=(
                            "Summarize the GitHub user information in a "
                            "structured format"
                        ),
                    )
                )
            else:
                response_data = response.json()
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status_code} {message}"
                raise InvokeError(msg)
        except InvokeError:
            raise
        except Exception as e:
            msg = f"GitHub API request failed: {e}"
            raise InvokeError(msg) from e
