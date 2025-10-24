"""Shared filter utilities for Twilio trigger events."""

from typing import Any

from dify_plugin.errors.trigger import EventIgnoreError


def _normalize_list(value: Any, lowercase: bool = True) -> list[str]:
    """
    Normalize various input types into a list of strings.

    Args:
        value: Input value (string, list, tuple, or None)
        lowercase: Whether to convert strings to lowercase

    Returns:
        List of normalized strings
    """
    if not value:
        return []

    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if item]
    else:
        items = [str(value).strip()]

    if lowercase:
        items = [item.lower() for item in items]

    return items


def check_from_number(payload: dict[str, Any], filter_value: str | None) -> None:
    """
    Check if message/call is from specific phone number(s).

    Args:
        payload: Webhook payload
        filter_value: Comma-separated phone numbers or single number

    Raises:
        EventIgnoreError: If sender doesn't match filter
    """
    if not filter_value:
        return

    from_numbers = _normalize_list(filter_value, lowercase=False)
    sender = payload.get("From", "")

    # Normalize phone numbers (remove spaces, dashes)
    normalized_senders = [num.replace(" ", "").replace("-", "") for num in from_numbers]
    normalized_from = sender.replace(" ", "").replace("-", "")

    if not any(normalized_from.endswith(num) or num in normalized_from for num in normalized_senders):
        raise EventIgnoreError()


def check_to_number(payload: dict[str, Any], filter_value: str | None) -> None:
    """
    Check if message/call is to specific phone number(s).

    Args:
        payload: Webhook payload
        filter_value: Comma-separated phone numbers or single number

    Raises:
        EventIgnoreError: If recipient doesn't match filter
    """
    if not filter_value:
        return

    to_numbers = _normalize_list(filter_value, lowercase=False)
    recipient = payload.get("To", "")

    normalized_recipients = [num.replace(" ", "").replace("-", "") for num in to_numbers]
    normalized_to = recipient.replace(" ", "").replace("-", "")

    if not any(normalized_to.endswith(num) or num in normalized_recipients for num in normalized_recipients):
        raise EventIgnoreError()


def check_body_contains(payload: dict[str, Any], filter_value: str | None, field: str = "Body") -> None:
    """
    Check if message body contains specific keywords.

    Args:
        payload: Webhook payload
        filter_value: Comma-separated keywords (case-insensitive)
        field: Field name to check (default: "Body")

    Raises:
        EventIgnoreError: If no keywords match
    """
    if not filter_value:
        return

    keywords = _normalize_list(filter_value, lowercase=True)
    body = payload.get(field, "").lower()

    if not any(keyword in body for keyword in keywords):
        raise EventIgnoreError()


def check_status(payload: dict[str, Any], filter_value: list[str] | str | None, field: str = "MessageStatus") -> None:
    """
    Check if status matches filter.

    Args:
        payload: Webhook payload
        filter_value: List of allowed statuses or comma-separated string
        field: Field name to check (default: "MessageStatus")

    Raises:
        EventIgnoreError: If status doesn't match
    """
    if not filter_value:
        return

    allowed_statuses = _normalize_list(filter_value, lowercase=True)
    current_status = payload.get(field, "").lower()

    if current_status not in allowed_statuses:
        raise EventIgnoreError()


def check_has_media(payload: dict[str, Any], filter_value: bool | None) -> None:
    """
    Check if message has media attachments.

    Args:
        payload: Webhook payload
        filter_value: True = must have media, False = must not have media, None = don't filter

    Raises:
        EventIgnoreError: If media presence doesn't match filter
    """
    if filter_value is None:
        return

    num_media = int(payload.get("NumMedia", 0))
    has_media = num_media > 0

    if filter_value != has_media:
        raise EventIgnoreError()


def check_direction(payload: dict[str, Any], filter_value: str | None) -> None:
    """
    Check call/message direction.

    Args:
        payload: Webhook payload
        filter_value: "inbound", "outbound-api", "outbound-dial", etc.

    Raises:
        EventIgnoreError: If direction doesn't match
    """
    if not filter_value:
        return

    allowed_directions = _normalize_list(filter_value, lowercase=True)
    direction = payload.get("Direction", "").lower()

    if direction not in allowed_directions:
        raise EventIgnoreError()
