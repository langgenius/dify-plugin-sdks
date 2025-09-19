import fnmatch
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class WorkflowRunTrigger(TriggerEvent):
    """
    GitHub Workflow Run Event Trigger

    This unified trigger handles all GitHub workflow run events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub workflow run event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (completed, in_progress, requested)
        - workflow_names: Filter by workflow names (supports wildcards)
        - conclusion_filter: Filter by workflow conclusion (for completed runs)
        - status_filter: Filter by workflow run status
        - branch_filter: Filter by branch names
        - duration_threshold: Alert on long-running workflows (minimum seconds, for completed runs)
        - exclude_actors: Exclude workflows triggered by these actors
        - event_types: Only trigger for specific event types
        - failure_only: Only trigger for failed workflows (for completed runs)
        - exclude_scheduled: Exclude scheduled workflow runs
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

        # Apply conclusion filter if specified (only for completed workflows)
        conclusion_filter = parameters.get("conclusion_filter")
        if conclusion_filter and action == "completed":
            conclusion = workflow_run.get("conclusion", "")
            if conclusion != conclusion_filter:
                raise TriggerIgnoreEventError(
                    f"Workflow concluded with '{conclusion}', not '{conclusion_filter}'"
                )

        # Apply status filter if specified
        status_filter = parameters.get("status_filter")
        if status_filter:
            status = workflow_run.get("status", "")
            if status != status_filter:
                raise TriggerIgnoreEventError(
                    f"Workflow status is '{status}', not '{status_filter}'"
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

        # Duration threshold filtering (only for completed workflows)
        duration_threshold = parameters.get("duration_threshold")
        if duration_threshold is not None and action == "completed":
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

        # Exclude actors filtering
        exclude_actors = parameters.get("exclude_actors", "")
        if exclude_actors:
            excluded = [a.strip() for a in exclude_actors.split(",") if a.strip()]
            if excluded:
                triggering_actor = workflow_run.get("triggering_actor", {}).get("login", "")
                actor = workflow_run.get("actor", {}).get("login", "")
                if triggering_actor in excluded or actor in excluded:
                    raise TriggerIgnoreEventError(
                        f"Workflow triggered by excluded actor: {triggering_actor or actor}"
                    )

        # Event types filtering
        event_types = parameters.get("event_types", "")
        if event_types:
            allowed_events = [e.strip() for e in event_types.split(",") if e.strip()]
            if allowed_events:
                event_type = workflow_run.get("event", "")
                if event_type not in allowed_events:
                    raise TriggerIgnoreEventError(
                        f"Workflow event '{event_type}' not in allowed types: {', '.join(allowed_events)}"
                    )

        # Failure only filtering (only for completed workflows)
        failure_only = parameters.get("failure_only", False)
        if failure_only and action == "completed":
            conclusion = workflow_run.get("conclusion", "")
            if conclusion not in ["failure", "timed_out", "cancelled"]:
                raise TriggerIgnoreEventError(f"Workflow concluded with '{conclusion}', not a failure")

        # Exclude scheduled runs filtering
        exclude_scheduled = parameters.get("exclude_scheduled", False)
        if exclude_scheduled:
            event_type = workflow_run.get("event", "")
            if event_type == "schedule":
                raise TriggerIgnoreEventError("Excluding scheduled workflow run")

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
            "action": action,
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