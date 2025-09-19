from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestReviewSubmittedTrigger(TriggerEvent):
    """
    GitHub Pull Request Review Pull Request Review Submitted Event Trigger

    This trigger handles GitHub pull request review submitted events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request review submitted event trigger with practical filtering

        Parameters:
        - review_state: Filter by review state (approved, changes_requested, commented)
        - author_type: Filter by author type (human_only, bot_only)
        - required_reviewers: Only from specific reviewers (comma-separated)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a submitted action
        action = payload.get("action", "")
        if action != "submitted":
            # This trigger only handles submitted events
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'submitted'")

        # Extract review, pull request, and repository information
        review = payload.get("review", {})
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Review state filtering
        review_state_filter = parameters.get("review_state")
        if review_state_filter:
            review_state = review.get("state", "").lower()
            if review_state != review_state_filter.lower():
                raise TriggerIgnoreEventError(
                    f"Review state '{review_state}' doesn't match required state '{review_state_filter}'"
                )

        # Author type filtering
        author_type_filter = parameters.get("author_type")
        if author_type_filter:
            reviewer_login = review.get("user", {}).get("login", "")
            reviewer_type = review.get("user", {}).get("type", "")
            is_bot = "[bot]" in reviewer_login or reviewer_type == "Bot"

            if author_type_filter == "human_only" and is_bot:
                raise TriggerIgnoreEventError(f"Ignoring review from bot: {reviewer_login}")
            elif author_type_filter == "bot_only" and not is_bot:
                raise TriggerIgnoreEventError(f"Ignoring review from human user: {reviewer_login}")

        # Required reviewers filtering
        required_reviewers = parameters.get("required_reviewers", "")
        if required_reviewers:
            allowed_reviewers = [r.strip() for r in required_reviewers.split(",") if r.strip()]
            if allowed_reviewers:
                reviewer_login = review.get("user", {}).get("login", "")
                # Check if reviewer is in the allowed list (support @team mentions)
                reviewer_matched = False
                for allowed in allowed_reviewers:
                    if allowed.startswith("@"):
                        # Team mention - would need additional API call to verify team membership
                        # For now, just check if the reviewer is mentioned
                        if reviewer_login == allowed[1:]:
                            reviewer_matched = True
                            break
                    elif reviewer_login == allowed:
                        reviewer_matched = True
                        break

                if not reviewer_matched:
                    raise TriggerIgnoreEventError(
                        f"Review from '{reviewer_login}' is not from required reviewers: {', '.join(allowed_reviewers)}"
                    )

        # Build variables for the workflow
        variables = {
            "review": {
                "id": review.get("id"),
                "body": review.get("body", ""),
                "state": review.get("state", ""),
                "html_url": review.get("html_url", ""),
                "submitted_at": review.get("submitted_at", ""),
                "author": {
                    "login": review.get("user", {}).get("login", ""),
                    "avatar_url": review.get("user", {}).get("avatar_url", ""),
                    "html_url": review.get("user", {}).get("html_url", ""),
                },
            },
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "html_url": pull_request.get("html_url", ""),
                "author": {
                    "login": pull_request.get("user", {}).get("login", ""),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", ""),
                    "html_url": pull_request.get("user", {}).get("html_url", ""),
                },
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