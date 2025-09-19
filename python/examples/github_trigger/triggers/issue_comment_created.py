from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent

from .filters import is_bot_user, parse_comma_list


class IssueCommentCreatedTrigger(TriggerEvent):
    """
    GitHub Issue Comment Created Event Trigger
    
    This trigger handles GitHub issue comment creation events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue comment created event trigger with practical filtering

        Parameters:
        - command_triggers: Only trigger for specific commands (e.g., /deploy)
        - exclude_bots: Exclude comments from bot accounts
        - issue_state: Filter by issue state (open/closed)
        - author_association: Filter by author's association with the repo
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")
        
        # Verify this is a created action
        action = payload.get("action", "")
        if action != "created":
            # This trigger only handles created events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'created\'")
        
        # Extract issue comment information
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        
        # Exclude bot comments if configured
        exclude_bots = parameters.get("exclude_bots", True)
        if exclude_bots and is_bot_user(sender):
            raise TriggerIgnoreEventError(f"Ignoring comment from bot: {sender.get('login', '')}")

        # Command trigger filtering
        command_triggers = parameters.get("command_triggers", "")
        if command_triggers:
            commands = parse_comma_list(command_triggers)
            if commands:
                comment_body = comment.get("body", "").strip()
                # Check if comment starts with any of the commands
                command_found = False
                for cmd in commands:
                    if comment_body.startswith(cmd):
                        command_found = True
                        break
                if not command_found:
                    raise TriggerIgnoreEventError(
                        f"Comment doesn't start with any command: {', '.join(commands)}"
                    )

        # Issue state filtering
        issue_state_filter = parameters.get("issue_state")
        if issue_state_filter:
            issue_state = issue.get("state", "")
            if issue_state != issue_state_filter:
                raise TriggerIgnoreEventError(
                    f"Issue is {issue_state}, not {issue_state_filter}"
                )

        # Author association filtering
        author_association_filter = parameters.get("author_association")
        if author_association_filter:
            author_association = comment.get("author_association", "")
            if author_association != author_association_filter:
                raise TriggerIgnoreEventError(
                    f"Comment author association is {author_association}, not {author_association_filter}"
                )
        
        # Check if this is a pull request
        is_pull_request = "pull_request" in issue
        
        # Extract labels
        labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in issue.get("labels", [])
        ]
        
        # Build variables for the workflow
        variables = {
            "comment": {
                "id": comment.get("id"),
                "body": comment.get("body", ""),
                "html_url": comment.get("html_url", ""),
                "created_at": comment.get("created_at", ""),
                "author": {
                    "login": comment.get("user", {}).get("login", ""),
                    "avatar_url": comment.get("user", {}).get("avatar_url", ""),
                    "html_url": comment.get("user", {}).get("html_url", ""),
                },
            },
            "issue": {
                "number": issue.get("number"),
                "title": issue.get("title", ""),
                "state": issue.get("state", ""),
                "html_url": issue.get("html_url", ""),
                "body": issue.get("body", ""),
                "labels": labels,
                "is_pull_request": is_pull_request,
                "created_at": issue.get("created_at", ""),
                "updated_at": issue.get("updated_at", ""),
                "assignees": [
                    {
                        "login": assignee.get("login", ""),
                        "avatar_url": assignee.get("avatar_url", ""),
                        "html_url": assignee.get("html_url", ""),
                    }
                    for assignee in issue.get("assignees", [])
                ],
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
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
            },
        }
        
        return Event(variables=variables)