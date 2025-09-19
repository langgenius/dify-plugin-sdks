import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PushTrigger(TriggerEvent):
    """
    GitHub Push Event Trigger

    This trigger handles GitHub push events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub push event trigger with advanced filtering

        Parameters:
        - branches: Filter by branch names (comma-separated, supports wildcards)
        - paths: Filter by file paths (comma-separated glob patterns)
        - ignore_patterns: Ignore commits with these patterns in messages
        - exclude_authors: Exclude commits from these authors
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract basic information
        ref = payload.get("ref", "")
        branch_name = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

        # Branch filtering
        branches_filter = parameters.get("branches", "")
        if branches_filter:
            allowed_branches = [b.strip() for b in branches_filter.split(",") if b.strip()]
            if allowed_branches:
                # Check if current branch matches any of the patterns
                branch_matched = False
                for pattern in allowed_branches:
                    if fnmatch.fnmatch(branch_name, pattern):
                        branch_matched = True
                        break
                if not branch_matched:
                    raise TriggerIgnoreEventError(
                        f"Branch '{branch_name}' doesn't match any allowed patterns: {', '.join(allowed_branches)}"
                    )

        # Author filtering
        exclude_authors = parameters.get("exclude_authors", "")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",") if a.strip()]
            pusher = payload.get("pusher", {}).get("name", "")
            if pusher in excluded:
                raise TriggerIgnoreEventError(f"Push from excluded author: {pusher}")

        # Commit message filtering
        ignore_patterns = parameters.get("ignore_patterns", "")
        if ignore_patterns:
            patterns = [p.strip() for p in ignore_patterns.split(",") if p.strip()]
            head_commit = payload.get("head_commit", {})
            commit_message = head_commit.get("message", "")
            for pattern in patterns:
                if pattern.lower() in commit_message.lower():
                    raise TriggerIgnoreEventError(
                        f"Commit message contains ignored pattern: '{pattern}'"
                    )

        # Path filtering
        paths_filter = parameters.get("paths", "")
        if paths_filter:
            patterns = [p.strip() for p in paths_filter.split(",") if p.strip()]
            if patterns:
                # Collect all changed files
                all_files = set()
                for commit in payload.get("commits", []):
                    all_files.update(commit.get("added", []))
                    all_files.update(commit.get("modified", []))
                    all_files.update(commit.get("removed", []))

                # Check if any file matches the patterns
                file_matched = False
                for file_path in all_files:
                    for pattern in patterns:
                        if fnmatch.fnmatch(file_path, pattern):
                            file_matched = True
                            break
                    if file_matched:
                        break

                if not file_matched and all_files:  # Only filter if there are files to check
                    raise TriggerIgnoreEventError(
                        f"No files match the path patterns: {', '.join(patterns)}"
                    )

        # Extract repository and sender information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Extract commits information
        commits = []
        for commit in payload.get("commits", []):
            commits.append({
                "id": commit.get("id", ""),
                "message": commit.get("message", ""),
                "timestamp": commit.get("timestamp", ""),
                "url": commit.get("url", ""),
                "author": {
                    "name": commit.get("author", {}).get("name", ""),
                    "email": commit.get("author", {}).get("email", ""),
                    "username": commit.get("author", {}).get("username", ""),
                },
                "committer": {
                    "name": commit.get("committer", {}).get("name", ""),
                    "email": commit.get("committer", {}).get("email", ""),
                    "username": commit.get("committer", {}).get("username", ""),
                },
                "added": commit.get("added", []),
                "removed": commit.get("removed", []),
                "modified": commit.get("modified", []),
            })

        # Build variables for the workflow
        variables = {
            "push": {
                "ref": ref,
                "branch": branch_name,
                "before": payload.get("before", ""),
                "after": payload.get("after", ""),
                "created": payload.get("created", False),
                "deleted": payload.get("deleted", False),
                "forced": payload.get("forced", False),
                "commits": commits,
                "head_commit": {
                    "id": payload.get("head_commit", {}).get("id", ""),
                    "message": payload.get("head_commit", {}).get("message", ""),
                    "timestamp": payload.get("head_commit", {}).get("timestamp", ""),
                    "url": payload.get("head_commit", {}).get("url", ""),
                    "author": {
                        "name": payload.get("head_commit", {}).get("author", {}).get("name", ""),
                        "email": payload.get("head_commit", {}).get("author", {}).get("email", ""),
                        "username": payload.get("head_commit", {}).get("author", {}).get("username", ""),
                    },
                },
                "compare": payload.get("compare", ""),
                "size": len(commits),
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "default_branch": repository.get("default_branch", ""),
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