import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class StarTrigger(TriggerEvent):
    """
    GitHub Star Event Trigger

    This unified trigger handles all GitHub star events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub star event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, deleted)
        - exclude_bots: Exclude bot users
        - user_filter: Filter by specific usernames (supports wildcards)
        - exclude_users: Exclude specific users (supports wildcards)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Get the action type
        action = payload.get("action", "")

        # Apply action filter
        action_filter = parameters.get("action_filter", [])
        if action_filter and action not in action_filter:
            raise TriggerIgnoreEventError(
                f"Action '{action}' not in filter list: {action_filter}"
            )

        # Extract star information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        starred_at = payload.get("starred_at", "")

        # Apply exclude bots filter
        exclude_bots = parameters.get("exclude_bots", False)
        if exclude_bots:
            sender_type = sender.get("type", "")
            sender_login = sender.get("login", "")
            is_bot = sender_type == "Bot" or "[bot]" in sender_login
            if is_bot:
                raise TriggerIgnoreEventError(f"Excluding bot user: {sender_login}")

        # Apply user filter
        user_filter = parameters.get("user_filter")
        if user_filter:
            user_patterns = [u.strip() for u in user_filter.split(",") if u.strip()]
            sender_login = sender.get("login", "")
            user_matched = False
            for pattern in user_patterns:
                if fnmatch.fnmatch(sender_login, pattern):
                    user_matched = True
                    break
            if not user_matched:
                raise TriggerIgnoreEventError(
                    f"User '{sender_login}' doesn't match patterns: {user_patterns}"
                )

        # Apply exclude users filter
        exclude_users = parameters.get("exclude_users")
        if exclude_users:
            exclude_patterns = [u.strip() for u in exclude_users.split(",") if u.strip()]
            sender_login = sender.get("login", "")
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(sender_login, pattern):
                    raise TriggerIgnoreEventError(f"Excluding user: {sender_login}")

        # Build variables for the workflow
        variables = {
            "action": action,
            "starred_at": starred_at,
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "fork": repository.get("fork", False),
                "created_at": repository.get("created_at", ""),
                "updated_at": repository.get("updated_at", ""),
                "pushed_at": repository.get("pushed_at", ""),
                "stargazers_count": repository.get("stargazers_count", 0),
                "watchers_count": repository.get("watchers_count", 0),
                "forks_count": repository.get("forks_count", 0),
                "language": repository.get("language", ""),
                "owner": {
                    "login": repository.get("owner", {}).get("login", ""),
                    "avatar_url": repository.get("owner", {}).get("avatar_url", ""),
                    "html_url": repository.get("owner", {}).get("html_url", ""),
                },
            },
            "sender": {
                "login": sender.get("login", ""),
                "avatar_url": sender.get("avatar_url", ""),
                "html_url": sender.get("html_url", ""),
                "type": sender.get("type", ""),
                "site_admin": sender.get("site_admin", False),
            },
        }

        return Event(variables=variables)