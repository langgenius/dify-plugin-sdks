import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class MemberTrigger(TriggerEvent):
    """
    GitHub Member Event Trigger

    This unified trigger handles all GitHub organization member events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub member event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (added, removed, edited)
        - member_role_filter: Filter by member role (admin, member, owner)
        - member_username_filter: Filter by member usernames (supports wildcards)
        - exclude_bots: Exclude bot members
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

        # Extract member information
        member = payload.get("member", {})
        organization = payload.get("organization", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply member role filter (note: role info might be in changes or separate field)
        member_role_filter = parameters.get("member_role_filter")
        if member_role_filter:
            # Role information might be available in different places depending on the event
            member_role = None

            # Check if there's role information in the payload
            if "role" in payload:
                member_role = payload.get("role")
            elif changes and "role" in changes and "to" in changes["role"]:
                member_role = changes["role"]["to"]
            elif changes and "permission" in changes and "to" in changes["permission"]:
                member_role = changes["permission"]["to"]

            if member_role and member_role != member_role_filter:
                raise TriggerIgnoreEventError(
                    f"Member role '{member_role}' doesn't match required role '{member_role_filter}'"
                )

        # Apply member username filter
        member_username_filter = parameters.get("member_username_filter")
        if member_username_filter:
            username_patterns = [u.strip() for u in member_username_filter.split(",") if u.strip()]
            member_login = member.get("login", "")
            username_matched = False
            for pattern in username_patterns:
                if fnmatch.fnmatch(member_login, pattern):
                    username_matched = True
                    break
            if not username_matched:
                raise TriggerIgnoreEventError(
                    f"Member username '{member_login}' doesn't match patterns: {username_patterns}"
                )

        # Apply exclude bots filter
        exclude_bots = parameters.get("exclude_bots", False)
        if exclude_bots:
            member_type = member.get("type", "")
            member_login = member.get("login", "")
            is_bot = member_type == "Bot" or "[bot]" in member_login
            if is_bot:
                raise TriggerIgnoreEventError(f"Excluding bot member: {member_login}")

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "role" in changes:
                changes_info["role"] = {"from": changes["role"].get("from", "")}
            if "permission" in changes:
                changes_info["permission"] = {"from": changes["permission"].get("from", "")}

        # Build variables for the workflow
        variables = {
            "action": action,
            "member": {
                "login": member.get("login", ""),
                "id": member.get("id"),
                "avatar_url": member.get("avatar_url", ""),
                "html_url": member.get("html_url", ""),
                "type": member.get("type", ""),
                "site_admin": member.get("site_admin", False),
            },
            "organization": {
                "login": organization.get("login", ""),
                "id": organization.get("id"),
                "avatar_url": organization.get("avatar_url", ""),
                "html_url": organization.get("html_url", ""),
                "description": organization.get("description", ""),
                "name": organization.get("name", ""),
                "company": organization.get("company", ""),
                "blog": organization.get("blog", ""),
                "location": organization.get("location", ""),
                "email": organization.get("email", ""),
                "public_repos": organization.get("public_repos", 0),
                "public_gists": organization.get("public_gists", 0),
                "followers": organization.get("followers", 0),
                "following": organization.get("following", 0),
                "created_at": organization.get("created_at", ""),
                "updated_at": organization.get("updated_at", ""),
            },
            "sender": {
                "login": sender.get("login", ""),
                "avatar_url": sender.get("avatar_url", ""),
                "html_url": sender.get("html_url", ""),
                "type": sender.get("type", ""),
            },
        }

        # Add changes info if present
        if changes_info:
            variables["changes"] = changes_info

        return Event(variables=variables)