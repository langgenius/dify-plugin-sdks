import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class DiscussionTrigger(TriggerEvent):
    """
    GitHub Discussion Event Trigger

    This unified trigger handles all GitHub discussion events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub discussion event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, deleted, edited, etc.)
        - categories: Filter by discussion categories
        - labels: Filter by discussion labels
        - exclude_authors: Exclude discussions from these authors
        - title_pattern: Filter by title patterns with wildcards
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

        # Extract discussion information
        discussion = payload.get("discussion", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply category filter
        categories_filter = parameters.get("categories")
        if categories_filter:
            allowed_categories = [c.strip() for c in categories_filter.split(",")]
            current_category = discussion.get("category", {}).get("name", "")
            if current_category not in allowed_categories:
                raise TriggerIgnoreEventError(
                    f"Discussion category '{current_category}' not in allowed categories: {allowed_categories}"
                )

        # Apply label filter
        labels_filter = parameters.get("labels")
        if labels_filter:
            required_labels = [l.strip() for l in labels_filter.split(",")]
            discussion_labels = [label.get("name", "") for label in discussion.get("labels", [])]
            if not any(label in discussion_labels for label in required_labels):
                raise TriggerIgnoreEventError(
                    f"Discussion doesn't have required labels: {required_labels}"
                )

        # Apply author exclusion filter
        exclude_authors = parameters.get("exclude_authors")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",")]
            author = discussion.get("user", {}).get("login", "")
            if author in excluded:
                raise TriggerIgnoreEventError(f"Author '{author}' is excluded")

        # Apply title pattern filter
        title_pattern_filter = parameters.get("title_pattern", "")
        if title_pattern_filter:
            allowed_patterns = [p.strip() for p in title_pattern_filter.split(",") if p.strip()]
            if allowed_patterns:
                title = discussion.get("title", "")
                # Check if title matches any of the patterns
                title_matched = False
                for pattern in allowed_patterns:
                    if fnmatch.fnmatch(title.lower(), pattern.lower()):
                        title_matched = True
                        break
                if not title_matched:
                    raise TriggerIgnoreEventError(
                        f"Title '{title}' doesn't match allowed patterns: {', '.join(allowed_patterns)}"
                    )

        # Extract labels
        labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in discussion.get("labels", [])
        ]

        # Extract category information
        category = None
        if discussion.get("category"):
            category = {
                "id": discussion["category"].get("id"),
                "name": discussion["category"].get("name", ""),
                "emoji": discussion["category"].get("emoji", ""),
                "description": discussion["category"].get("description", ""),
                "slug": discussion["category"].get("slug", ""),
            }

        # Extract answer information (if answered)
        answer_html_url = discussion.get("answer_html_url", "")
        answer_chosen_at = discussion.get("answer_chosen_at", "")
        answer_chosen_by = None
        if discussion.get("answer_chosen_by"):
            answer_chosen_by = {
                "login": discussion["answer_chosen_by"].get("login", ""),
                "avatar_url": discussion["answer_chosen_by"].get("avatar_url", ""),
                "html_url": discussion["answer_chosen_by"].get("html_url", ""),
            }

        # Extract changes information (for edited/category_changed actions)
        changes_info = {}
        if action in ["edited", "category_changed"] and changes:
            if "title" in changes:
                changes_info["title"] = {"from": changes["title"].get("from", "")}
            if "body" in changes:
                changes_info["body"] = {"from": changes["body"].get("from", "")}
            if "category" in changes:
                changes_info["category"] = {"from": changes["category"].get("from", {})}

        # Build variables for the workflow
        variables = {
            "action": action,
            "discussion": {
                "id": discussion.get("id"),
                "number": discussion.get("number"),
                "title": discussion.get("title", ""),
                "body": discussion.get("body", ""),
                "state": discussion.get("state", ""),
                "html_url": discussion.get("html_url", ""),
                "category": category,
                "user": {
                    "login": discussion.get("user", {}).get("login", ""),
                    "avatar_url": discussion.get("user", {}).get("avatar_url", ""),
                    "html_url": discussion.get("user", {}).get("html_url", ""),
                },
                "labels": labels,
                "locked": discussion.get("locked", False),
                "created_at": discussion.get("created_at", ""),
                "updated_at": discussion.get("updated_at", ""),
                "comments": discussion.get("comments", 0),
                "answer_html_url": answer_html_url,
                "answer_chosen_at": answer_chosen_at,
                "answer_chosen_by": answer_chosen_by,
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
                "default_branch": repository.get("default_branch", ""),
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