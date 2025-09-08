import requests

from dify_plugin.entities import I18nObject, ParameterOption


def fetch_repositories(access_token: str) -> list[ParameterOption]:
    if not access_token:
        raise ValueError("access_tokens is required")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    options: list[ParameterOption] = []
    per_page = 100
    page = 1

    while True:
        params = {
            "per_page": per_page,
            "page": page,
            # Include all repositories the user can access
            "affiliation": "owner,collaborator,organization_member",
            "sort": "full_name",
            "direction": "asc",
        }

        response = requests.get("https://api.github.com/user/repos", headers=headers, params=params, timeout=10)

        if response.status_code != 200:
            try:
                err = response.json()
                message = err.get("message", str(err))
            except Exception:
                message = response.text
            raise ValueError(f"Failed to fetch repositories from GitHub: {message}")

        repos = response.json() or []
        if not isinstance(repos, list):
            raise ValueError("Unexpected response format from GitHub API when fetching repositories")

        for repo in repos:
            full_name = repo.get("full_name")  # e.g., owner/repo
            owner = repo.get("owner") or {}
            avatar_url = owner.get("avatar_url")
            if full_name:
                options.append(
                    ParameterOption(
                        value=full_name,
                        label=I18nObject(en_US=full_name),
                        icon=avatar_url,
                    )
                )

        # pagination break condition
        if len(repos) < per_page:
            break

        page += 1

    return options
