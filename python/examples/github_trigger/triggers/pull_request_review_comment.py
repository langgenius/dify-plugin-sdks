import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestReviewCommentTrigger(TriggerEvent):
    """
    GitHub Pull Request Review Comment Event Trigger

    This unified trigger handles all GitHub pull request review comment events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request review comment event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, edited, deleted)
        - author_type: Filter by author type (human_only, bot_only)
        - required_commenters: Only from specific commenters (comma-separated)
        - target_branches: Filter by target branch (comma-separated, supports wildcards)
        - labels: Filter by PR labels (comma-separated)
        - exclude_pr_authors: Exclude comments on PRs from these authors (comma-separated)
        - min_body_length: Minimum comment body length for meaningful comments
        - mention_keywords: Only trigger if comment mentions these keywords
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

        # Extract comment, pull request, and repository information
        comment = payload.get("comment", {})
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Author type filtering
        author_type_filter = parameters.get("author_type")
        if author_type_filter:
            commenter_login = comment.get("user", {}).get("login", "")
            commenter_type = comment.get("user", {}).get("type", "")
            is_bot = "[bot]" in commenter_login or commenter_type == "Bot"

            if author_type_filter == "human_only" and is_bot:
                raise TriggerIgnoreEventError(f"Ignoring comment from bot: {commenter_login}")
            elif author_type_filter == "bot_only" and not is_bot:
                raise TriggerIgnoreEventError(f"Ignoring comment from human user: {commenter_login}")

        # Required commenters filtering
        required_commenters = parameters.get("required_commenters", "")
        if required_commenters:
            allowed_commenters = [r.strip() for r in required_commenters.split(",") if r.strip()]
            if allowed_commenters:
                commenter_login = comment.get("user", {}).get("login", "")
                # Check if commenter is in the allowed list (support @team mentions)
                commenter_matched = False
                for allowed in allowed_commenters:
                    if allowed.startswith("@"):
                        # Team mention - would need additional API call to verify team membership
                        # For now, just check if the commenter is mentioned
                        if commenter_login == allowed[1:]:
                            commenter_matched = True
                            break
                    elif commenter_login == allowed:
                        commenter_matched = True
                        break

                if not commenter_matched:
                    raise TriggerIgnoreEventError(
                        f"Comment from '{commenter_login}' is not from required commenters: {', '.join(allowed_commenters)}"
                    )

        # Target branch filtering
        target_branches = parameters.get("target_branches", "")
        if target_branches:
            allowed_branches = [b.strip() for b in target_branches.split(",") if b.strip()]
            if allowed_branches:
                base_branch = pull_request.get("base", {}).get("ref", "")
                branch_matched = False
                for pattern in allowed_branches:
                    if fnmatch.fnmatch(base_branch, pattern):
                        branch_matched = True
                        break
                if not branch_matched:
                    raise TriggerIgnoreEventError(
                        f"PR targets '{base_branch}' which doesn't match allowed patterns: {', '.join(allowed_branches)}"
                    )

        # Label filtering
        labels_filter = parameters.get("labels", "")
        if labels_filter:
            required_labels = [label.strip() for label in labels_filter.split(",") if label.strip()]
            if required_labels:
                pr_labels = [label.get("name", ") for label in pull_request.get("labels", [])]
                has_required_label = any(label in pr_labels for label in required_labels)
                if not has_required_label:
                    raise TriggerIgnoreEventError(
                        f"PR doesn't have any of the required labels: {', '.join(required_labels)}"
                    )

        # Exclude PR authors filtering
        exclude_pr_authors = parameters.get("exclude_pr_authors", "")
        if exclude_pr_authors:
            excluded = [a.strip() for a in exclude_pr_authors.split(",") if a.strip()]
            pr_author = pull_request.get("user", {}).get("login", "")
            if pr_author in excluded:
                raise TriggerIgnoreEventError(f"Comment on PR by excluded author: {pr_author}")

        # Minimum body length filtering
        min_body_length = parameters.get("min_body_length")
        if min_body_length is not None:
            try:
                min_length = int(min_body_length)
                comment_body = comment.get("body", "")
                if len(comment_body.strip()) < min_length:
                    raise TriggerIgnoreEventError(
                        f"Comment body too short ({len(comment_body.strip())} chars, minimum {min_length})"
                    )
            except (ValueError, TypeError):
                pass  # Invalid min_body_length value, skip filtering

        # Mention keywords filtering
        mention_keywords = parameters.get("mention_keywords", "")
        if mention_keywords:
            keywords = [k.strip().lower() for k in mention_keywords.split(",") if k.strip()]
            comment_body = comment.get("body", ").lower()
            has_keyword = any(keyword in comment_body for keyword in keywords)
            if not has_keyword:
                raise TriggerIgnoreEventError(
                    f"Comment doesn't mention any of the required keywords: {keywords}"
                )

        # Extract labels
        labels = [
            {
                "name": label.get("name", "),
                "color": label.get("color", "),
                "description": label.get("description", "),
            }
            for label in pull_request.get("labels", [])
        ]

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "body" in changes:
                changes_info["body"] = {"from": changes["body"].get("from", ")}

        # Build variables for the workflow
        variables = {
            "action": action,
            "comment": {
                "id": comment.get("id"),
                "body": comment.get("body", "),
                "html_url": comment.get("html_url", "),
                "created_at": comment.get("created_at", "),
                "updated_at": comment.get("updated_at", "),
                "author": {
                    "login": comment.get("user", {}).get("login", "),
                    "avatar_url": comment.get("user", {}).get("avatar_url", "),
                    "html_url": comment.get("user", {}).get("html_url", "),
                    "type": comment.get("user", {}).get("type", "),
                },
                "diff_hunk": comment.get("diff_hunk", "),
                "path": comment.get("path", "),
                "position": comment.get("position"),
                "original_position": comment.get("original_position"),
                "commit_id": comment.get("commit_id", "),
                "original_commit_id": comment.get("original_commit_id", "),
                "line": comment.get("line"),
                "original_line": comment.get("original_line"),
                "side": comment.get("side", "),
                "start_line": comment.get("start_line"),
                "start_side": comment.get("start_side", "),
                "in_reply_to_id": comment.get("in_reply_to_id"),
            },
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", "),
                "body": pull_request.get("body", "),
                "state": pull_request.get("state", "),
                "html_url": pull_request.get("html_url", "),
                "created_at": pull_request.get("created_at", "),
                "updated_at": pull_request.get("updated_at", "),
                "draft": pull_request.get("draft", False),
                "labels": labels,
                "assignees": [
                    {
                        "login": assignee.get("login", "),
                        "avatar_url": assignee.get("avatar_url", "),
                        "html_url": assignee.get("html_url", "),
                    }
                    for assignee in pull_request.get("assignees", [])
                ],
                "author": {
                    "login": pull_request.get("user", {}).get("login", "),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", "),
                    "html_url": pull_request.get("user", {}).get("html_url", "),
                },
                "head": {
                    "ref": pull_request.get("head", {}).get("ref", "),
                    "sha": pull_request.get("head", {}).get("sha", "),
                    "repo_name": pull_request.get("head", {}).get("repo", {}).get("full_name", "),
                },
                "base": {
                    "ref": pull_request.get("base", {}).get("ref", "),
                    "sha": pull_request.get("base", {}).get("sha", "),
                    "repo_name": pull_request.get("base", {}).get("repo", {}).get("full_name", "),
                },
            },
            "repository": {
                "name": repository.get("name", "),
                "full_name": repository.get("full_name", "),
                "html_url": repository.get("html_url", "),
                "description": repository.get("description", "),
                "private": repository.get("private", False),
                "owner": {
                    "login": repository.get("owner", {}).get("login", "),
                    "avatar_url": repository.get("owner", {}).get("avatar_url", "),
                    "html_url": repository.get("owner", {}).get("html_url", "),
                },
            },
            "sender": {
                "login": sender.get("login", "),
                "avatar_url": sender.get("avatar_url", "),
                "html_url": sender.get("html_url", "),
                "type": sender.get("type", "),
            },
        }

        # Add changes info if present
        if changes_info:
            variables["changes"] = changes_info

        return Event(variables=variables)