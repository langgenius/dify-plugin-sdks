import json
from collections.abc import Generator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import urllib3_future

from dify_plugin import Tool
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage

DESCRIPTION_PREVIEW_LENGTH = 100
GITHUB_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DISPLAY_DATE_FORMAT = "%Y-%m-%d"


def _format_github_date(value: str) -> str:
    parsed = datetime.strptime(value, GITHUB_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    return parsed.strftime(DISPLAY_DATE_FORMAT)


class GithubRepositoriesTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        top_n = tool_parameters.get("top_n", 5)
        query = tool_parameters.get("query", "")
        credential_type = self.runtime.credential_type
        if not query:
            yield self.create_text_message("Please input symbol")
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
                # fixed api version
                "X-GitHub-Api-Version": "2022-11-28",
            }
            response = urllib3_future.request(
                "GET",
                "https://api.github.com/search/repositories",
                fields={
                    "q": query,
                    "sort": "stars",
                    "per_page": top_n,
                    "order": "desc",
                },
                headers=headers,
                timeout=10,
            )
            response_data = response.json()

            items = response_data.get("items")
            if response.status != HTTPStatus.OK or not isinstance(items, list):
                yield self.create_text_message(response_data.get("message"))
                return
            if not items:
                yield self.create_text_message(
                    f"No items related to {query} were found."
                )
                return

            contents = []
            for item in items:
                description = item["description"] or ""
                if len(description) > DESCRIPTION_PREVIEW_LENGTH:
                    description = description[:DESCRIPTION_PREVIEW_LENGTH] + "..."
                contents.append({
                    "owner": item["owner"]["login"],
                    "name": item["name"],
                    "description": description,
                    "url": item["html_url"],
                    "star": item["watchers"],
                    "forks": item["forks"],
                    "updated": _format_github_date(item["updated_at"]),
                })
            yield self.create_text_message(
                self.session.model.summary.invoke(
                    text=json.dumps(contents, ensure_ascii=False),
                    instruction="Summarize the text",
                )
            )
        except Exception as exc:
            yield self.create_text_message(
                f"GitHub API Key and Api Version is invalid. {exc}"
            )

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        del parameter
        return [
            ParameterOption(
                value="iamjoel",
                label=I18nObject(en_us="Joel"),
                icon="https://avatars.githubusercontent.com/u/2120155?s=40&v=4",
            ),
            ParameterOption(
                value="yeuoly",
                label=I18nObject(en_us="Yeuoly"),
                icon="https://avatars.githubusercontent.com/u/45712896?s=60&v=4",
            ),
        ]
