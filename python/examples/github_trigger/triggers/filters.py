"""
Common filtering utilities for GitHub triggers
"""

import fnmatch
from typing import List


def check_wildcard_match(value: str, patterns: List[str]) -> bool:
    """
    Check if value matches any of the wildcard patterns

    Args:
        value: The value to check
        patterns: List of patterns (supports wildcards)

    Returns:
        True if value matches any pattern
    """
    for pattern in patterns:
        if fnmatch.fnmatch(value, pattern):
            return True
    return False


def parse_comma_list(value: str) -> List[str]:
    """
    Parse comma-separated string into list of trimmed values

    Args:
        value: Comma-separated string

    Returns:
        List of non-empty trimmed strings
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def check_label_match(labels: List[dict], required_labels: List[str]) -> bool:
    """
    Check if any required label is present

    Args:
        labels: List of label dictionaries with 'name' field
        required_labels: List of required label names

    Returns:
        True if any required label is present
    """
    if not required_labels:
        return True

    label_names = [label.get("name", "") for label in labels]
    return any(label in label_names for label in required_labels)


def is_bot_user(user: dict) -> bool:
    """
    Check if a user is a bot

    Args:
        user: User dictionary with 'login' and 'type' fields

    Returns:
        True if user is a bot
    """
    login = user.get("login", "")
    user_type = user.get("type", "")
    return "[bot]" in login or user_type == "Bot"


def check_keyword_match(text: str, keywords: List[str]) -> bool:
    """
    Check if text contains any of the keywords (case-insensitive)

    Args:
        text: Text to search in
        keywords: List of keywords to search for

    Returns:
        True if any keyword is found
    """
    if not keywords:
        return True

    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)
