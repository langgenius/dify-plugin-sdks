import json
from collections.abc import Generator
from http import HTTPStatus
from typing import Any

import urllib3_future

from dify_plugin import Tool
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.errors.model import InvokeError


class GithubSearchCodeTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        invoke tools
        """
        query = tool_parameters.get("query", "")
        per_page = tool_parameters.get("per_page", 10)
        sort = tool_parameters.get("sort", "")
        order = tool_parameters.get("order", "desc")

        credential_type = self.runtime.credential_type

        if not query:
            yield self.create_text_message("Please input search query")
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
        params = {"q": query, "per_page": per_page, "order": order}
        if sort:
            params["sort"] = sort

        try:
            response = urllib3_future.request(
                "GET",
                headers=headers,
                url="https://api.github.com/search/code",
                fields=params,
                timeout=10,
            )
            response_data = response.json()
            if response.status != HTTPStatus.OK:
                message = response_data.get("message", "Unknown error")
                msg = f"Request failed: {response.status} {message}"
                raise InvokeError(msg)

            total_count = response_data.get("total_count", 0)
            items = response_data.get("items", [])
            search_results = []
            for item in items:
                repository = item.get("repository", {})
                owner = repository.get("owner", {})
                result_info = {
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "sha": item.get("sha", "")[:7],
                    "url": item.get("html_url", ""),
                    "git_url": item.get("git_url", ""),
                    "download_url": item.get("download_url", ""),
                    "score": item.get("score", 0),
                    "repository": {
                        "id": repository.get("id", 0),
                        "name": repository.get("name", ""),
                        "full_name": repository.get("full_name", ""),
                        "url": repository.get("html_url", ""),
                        "description": repository.get("description", ""),
                        "language": repository.get("language", ""),
                        "stars": repository.get("stargazers_count", 0),
                        "forks": repository.get("forks_count", 0),
                        "is_private": repository.get("private", False),
                        "owner": {
                            "login": owner.get("login", ""),
                            "type": owner.get("type", ""),
                        },
                    },
                    "text_matches": [
                        {
                            "fragment": match.get("fragment", ""),
                            "matches": [
                                {
                                    "text": matched_text.get("text", ""),
                                    "indices": matched_text.get("indices", []),
                                }
                                for matched_text in match.get("matches", [])
                            ],
                        }
                        for match in item.get("text_matches", [])
                    ],
                }
                search_results.append(result_info)

            result = {
                "total_count": total_count,
                "query": query,
                "results": search_results,
            }

            if not search_results:
                yield self.create_text_message(f"No code found for query: {query}")
            else:
                yield self.create_text_message(
                    self.session.model.summary.invoke(
                        text=json.dumps(result, ensure_ascii=False),
                        instruction=(
                            "Summarize the GitHub code search results "
                            "in a structured format"
                        ),
                    )
                )
        except InvokeError:
            raise
        except Exception as exc:
            msg = f"GitHub API request failed: {exc}"
            raise InvokeError(msg) from exc
