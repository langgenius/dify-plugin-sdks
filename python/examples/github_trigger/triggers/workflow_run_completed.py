import fnmatch
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class WorkflowRunCompletedTrigger(TriggerEvent):
    """
    GitHub Workflow Run Completed Event Trigger

    This trigger handles GitHub workflow run completed events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub workflow run completed event trigger with practical filtering

        Parameters:
        - workflow_names: Filter by workflow names (comma-separated, supports wildcards)
        - conclusion_filter: Filter by workflow conclusion
        - branch_filter: Filter by branch names
        - duration_threshold: Alert on long-running workflows
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a completed action
        action = payload.get("action", "")
        if action != "completed":
            # This trigger only handles completed events
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'completed'")

        # Extract workflow run information
        workflow_run = payload.get("workflow_run", {})
        workflow = payload.get("workflow", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Workflow name filtering with wildcard support
        workflow_names_filter = parameters.get("workflow_names", "")
        if workflow_names_filter:
            allowed_names = [n.strip() for n in workflow_names_filter.split(",") if n.strip()]
            if allowed_names:
                workflow_name = workflow.get("name", "")
                # Check if workflow name matches any of the patterns
                name_matched = False
                for pattern in allowed_names:
                    if fnmatch.fnmatch(workflow_name, pattern):
                        name_matched = True
                        break
                if not name_matched:
                    raise TriggerIgnoreEventError(
                        f"Workflow '{workflow_name}' doesn't match allowed patterns: {', '.join(allowed_names)}"
                    )

        # Apply conclusion filter if specified
        conclusion_filter = parameters.get("conclusion_filter")
        if conclusion_filter:
            conclusion = workflow_run.get("conclusion", "")
            if conclusion != conclusion_filter:
                raise TriggerIgnoreEventError(
                    f"Workflow concluded with '{conclusion}', not '{conclusion_filter}'"
                )

        # Branch filtering
        branch_filter = parameters.get("branch_filter", "")
        if branch_filter:
            allowed_branches = [b.strip() for b in branch_filter.split(",") if b.strip()]
            if allowed_branches:
                head_branch = workflow_run.get("head_branch", "")
                # Check if branch matches any of the patterns
                branch_matched = False
                for pattern in allowed_branches:
                    if fnmatch.fnmatch(head_branch, pattern):
                        branch_matched = True
                        break
                if not branch_matched:
                    raise TriggerIgnoreEventError(
                        f"Workflow on branch '{head_branch}' doesn't match allowed patterns: {', '.join(allowed_branches)}"
                    )

        # Duration threshold filtering
        duration_threshold = parameters.get("duration_threshold")
        if duration_threshold is not None:
            try:
                threshold_seconds = int(duration_threshold)
                # Calculate workflow duration
                started_at = workflow_run.get("run_started_at", "")
                updated_at = workflow_run.get("updated_at", "")
                if started_at and updated_at:
                    try:
                        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                        end_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        duration_seconds = (end_time - start_time).total_seconds()

                        if duration_seconds <= threshold_seconds:
                            raise TriggerIgnoreEventError(
                                f"Workflow completed in {duration_seconds:.0f}s, under threshold of {threshold_seconds}s"
                            )
                    except (ValueError, TypeError):
                        pass  # Unable to parse dates, skip filtering
            except ValueError:
                pass  # Invalid threshold value, skip filtering

        # Extract pull requests information
        pull_requests = []
        for pr in workflow_run.get("pull_requests", []):
            pull_requests.append({
                "number": pr.get("number"),
                "head": {
                    "ref": pr.get("head", {}).get("ref", ""),
                    "sha": pr.get("head", {}).get("sha", ""),
                },
                "base": {
                    "ref": pr.get("base", {}).get("ref", ""),
                    "sha": pr.get("base", {}).get("sha", ""),
                },
            })

        # Build variables for the workflow
        variables = {
            "workflow_run": {
                "id": workflow_run.get("id"),
                "name": workflow_run.get("name", ""),
                "display_title": workflow_run.get("display_title", ""),
                "run_number": workflow_run.get("run_number"),
                "run_attempt": workflow_run.get("run_attempt"),
                "status": workflow_run.get("status", ""),
                "conclusion": workflow_run.get("conclusion", ""),
                "workflow_id": workflow_run.get("workflow_id"),
                "url": workflow_run.get("url", ""),
                "html_url": workflow_run.get("html_url", ""),
                "created_at": workflow_run.get("created_at", ""),
                "updated_at": workflow_run.get("updated_at", ""),
                "run_started_at": workflow_run.get("run_started_at", ""),
                "jobs_url": workflow_run.get("jobs_url", ""),
                "logs_url": workflow_run.get("logs_url", ""),
                "check_suite_url": workflow_run.get("check_suite_url", ""),
                "artifacts_url": workflow_run.get("artifacts_url", ""),
                "cancel_url": workflow_run.get("cancel_url", ""),
                "rerun_url": workflow_run.get("rerun_url", ""),
                "head_branch": workflow_run.get("head_branch", ""),
                "head_sha": workflow_run.get("head_sha", ""),
                "event": workflow_run.get("event", ""),
                "actor": {
                    "login": workflow_run.get("actor", {}).get("login", ""),
                    "avatar_url": workflow_run.get("actor", {}).get("avatar_url", ""),
                    "html_url": workflow_run.get("actor", {}).get("html_url", ""),
                },
                "triggering_actor": {
                    "login": workflow_run.get("triggering_actor", {}).get("login", ""),
                    "avatar_url": workflow_run.get("triggering_actor", {}).get("avatar_url", ""),
                    "html_url": workflow_run.get("triggering_actor", {}).get("html_url", ""),
                },
                "pull_requests": pull_requests,
            },
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name", ""),
                "path": workflow.get("path", ""),
                "state": workflow.get("state", ""),
                "created_at": workflow.get("created_at", ""),
                "updated_at": workflow.get("updated_at", ""),
                "url": workflow.get("url", ""),
                "html_url": workflow.get("html_url", ""),
                "badge_url": workflow.get("badge_url", ""),
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