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

RELEASE_BODY_PREVIEW_LENGTH = 300
GITHUB_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DISPLAY_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_github_timestamp(value: str) -> str:
    parsed = datetime.strptime(value, GITHUB_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    return parsed.strftime(DISPLAY_DATETIME_FORMAT)


class GithubRepositoryReleasesTool(Tool):
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
                "Content-Type": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            s = requests.session()
            api_domain = "https://api.github.com"
            url = f"{api_domain}/repos/{owner}/{repo}/releases"

            params = {"per_page": per_page}

            response = s.request(
                method="GET",
                headers=headers,
                url=url,
                params=params,
            )

            if response.status_code == HTTPStatus.OK:
                response_data = response.json()

                releases = []
                for release in response_data:
                    release_info = {
                        "id": release.get("id", 0),
                        "tag_name": release.get("tag_name", ""),
                        "name": release.get("name", ""),
                        "body": (release.get("body", "") or "")[
                            :RELEASE_BODY_PREVIEW_LENGTH
                        ]
                        + "..."
                        if len(release.get("body", "") or "")
                        > RELEASE_BODY_PREVIEW_LENGTH
                        else (release.get("body", "") or ""),
                        "url": release.get("html_url", ""),
                        "tarball_url": release.get("tarball_url", ""),
                        "zipball_url": release.get("zipball_url", ""),
                        "author": release.get("author", {}).get("login", ""),
                        "draft": release.get("draft", False),
                        "prerelease": release.get("prerelease", False),
                        "assets": [
                            {
                                "name": asset.get("name", ""),
                                "size": asset.get("size", 0),
                                "download_count": asset.get("download_count", 0),
                                "download_url": asset.get("browser_download_url", ""),
                            }
                            for asset in release.get("assets", [])
                        ],
                        "created_at": _format_github_timestamp(
                            release.get("created_at", "")
                        )
                        if release.get("created_at")
                        else "",
                        "published_at": _format_github_timestamp(
                            release.get("published_at", "")
                        )
                        if release.get("published_at")
                        else "",
                    }
                    releases.append(release_info)

                s.close()

                if not releases:
                    yield self.create_text_message(
                        f"No releases found in {owner}/{repo}"
                    )
                else:
                    yield self.create_text_message(
                        self.session.model.summary.invoke(
                            text=json.dumps(releases, ensure_ascii=False),
                            instruction=(
                                "Summarize the GitHub releases in a structured format"
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
