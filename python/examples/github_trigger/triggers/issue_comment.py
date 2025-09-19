from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueCommentTrigger(TriggerEvent):
    """
    GitHub Issue Comment Event Trigger

    This unified trigger handles GitHub issue comment events (created, edited, deleted)
    and extracts relevant information from the webhook payload to provide as variables
    to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue comment event trigger

        Parameters:
        - action_filter: Filter by action type (all, created, edited, deleted)
        - command_triggers: Only trigger if comment starts with these commands
        - exclude_bots: Ignore comments from bot accounts
        - issue_state: Filter by issue state
        - author_association: Filter by author association type
        - exclude_issue_authors: Ignore comments on issues from these authors
        - min_comment_length: Minimum comment length to trigger
        - keyword_filter: Only trigger if comment contains these keywords
        - mention_required: Only trigger if comment mentions these users
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Get the action type
        action = payload.get("action", "")

        # Apply action filter
        action_filter = parameters.get("action_filter", "all")
        if action_filter != "all" and action_filter != action:
            raise TriggerIgnoreEventError(
                f"Action '{action}' does not match filter '{action_filter}'"
            )

        # Extract comment, issue, repository, and sender information
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply exclude_bots filter
        if parameters.get("exclude_bots", True):
            if sender.get("type") == "Bot":
                raise TriggerIgnoreEventError("Bot comments are excluded")

        # Apply issue_state filter
        issue_state_filter = parameters.get("issue_state", "all")
        if issue_state_filter != "all":
            issue_state = issue.get("state")
            if issue_state != issue_state_filter:
                raise TriggerIgnoreEventError(
                    f"Issue state '{issue_state}' does not match filter '{issue_state_filter}'"
                )

        # Apply author_association filter
        author_association_filter = parameters.get("author_association", "all")
        if author_association_filter != "all":
            author_association = comment.get("author_association")
            if author_association != author_association_filter:
                raise TriggerIgnoreEventError(
                    f"Author association '{author_association}' does not match filter"
                )

        # Apply exclude_issue_authors filter
        exclude_authors = parameters.get("exclude_issue_authors")
        if exclude_authors:
            excluded_list = [a.strip() for a in exclude_authors.split(",")]
            issue_author = issue.get("user", {}).get("login", "")
            if issue_author in excluded_list:
                raise TriggerIgnoreEventError(
                    f"Issue author '{issue_author}' is in the exclude list"
                )

        # Get comment body (will be empty for deleted action)
        comment_body = comment.get("body", "")

        # Apply filters that only work on created/edited actions
        if action in ["created", "edited"]:
            # Apply command_triggers filter
            command_triggers = parameters.get("command_triggers")
            if command_triggers:
                commands = [cmd.strip() for cmd in command_triggers.split(",")]
                if not any(comment_body.startswith(cmd) for cmd in commands):
                    raise TriggerIgnoreEventError(
                        "Comment does not start with any required command"
                    )

            # Apply min_comment_length filter
            min_length = parameters.get("min_comment_length")
            if min_length is not None:
                if len(comment_body) < int(min_length):
                    raise TriggerIgnoreEventError(
                        f"Comment length {len(comment_body)} is less than minimum {min_length}"
                    )

            # Apply keyword_filter
            keywords = parameters.get("keyword_filter")
            if keywords:
                keyword_list = [kw.strip().lower() for kw in keywords.split(",")]
                comment_lower = comment_body.lower()
                if not any(kw in comment_lower for kw in keyword_list):
                    raise TriggerIgnoreEventError(
                        "Comment does not contain any required keywords"
                    )

            # Apply mention_required filter
            mentions = parameters.get("mention_required")
            if mentions:
                mention_list = [f"@{m.strip()}" for m in mentions.split(",")]
                if not any(mention in comment_body for mention in mention_list):
                    raise TriggerIgnoreEventError(
                        "Comment does not mention any required users"
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

        # Extract the previous body from changes if available (for edited action)
        body_from = ""
        if action == "edited" and changes and "body" in changes:
            body_from = changes["body"].get("from", "")

        # Build variables for the workflow
        variables = {
            "action": action,
            "comment": {
                "id": comment.get("id"),
                "body": comment_body,
                "body_from": body_from,
                "html_url": comment.get("html_url", ""),
                "created_at": comment.get("created_at", ""),
                "updated_at": comment.get("updated_at", ""),
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