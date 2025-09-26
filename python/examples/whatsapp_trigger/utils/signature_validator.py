"""
WhatsApp Webhook Signature Validation Utility

This module provides functions to validate webhook signatures from WhatsApp/Meta
to ensure the authenticity of incoming webhook requests.
"""

import hashlib
import hmac
import time

from werkzeug import Request


def validate_signature(request: Request, app_secret: str, max_age_seconds: int = 300) -> bool:
    """
    Validate WhatsApp webhook signature using HMAC-SHA256

    Args:
        request: The incoming webhook request
        app_secret: The app secret from Meta App Dashboard
        max_age_seconds: Maximum age of the request in seconds (default 5 minutes)

    Returns:
        bool: True if signature is valid, False otherwise
    """
    # Get the signature header
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        return False

    # Extract the signature from the header (format: "sha256=<signature>")
    if not signature_header.startswith("sha256="):
        return False

    received_signature = signature_header[7:]  # Remove "sha256=" prefix

    # Get the raw request body
    raw_body = request.get_data()

    # Calculate expected signature
    expected_signature = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    # Optional: Check timestamp to prevent replay attacks
    # WhatsApp doesn't include timestamp in standard webhooks,
    # but you can add this if implementing custom timestamp handling

    # Compare signatures using constant-time comparison
    return hmac.compare_digest(received_signature, expected_signature)


def validate_verify_token(request: Request, verify_token: str) -> bool:
    """
    Validate WhatsApp webhook verification token during initial setup

    Args:
        request: The incoming verification request
        verify_token: The custom verify token you set

    Returns:
        bool: True if verify token matches, False otherwise
    """
    hub_mode = request.args.get("hub.mode")
    hub_token = request.args.get("hub.verify_token")
    hub_challenge = request.args.get("hub.challenge")

    # Check all required parameters are present
    if not all([hub_mode, hub_token, hub_challenge]):
        return False

    # Verify mode is "subscribe" and token matches
    return hub_mode == "subscribe" and hub_token == verify_token


def calculate_signature(payload: bytes, app_secret: str) -> str:
    """
    Calculate HMAC-SHA256 signature for a payload

    Args:
        payload: The payload bytes to sign
        app_secret: The app secret from Meta App Dashboard

    Returns:
        str: The calculated signature in format "sha256=<signature>"
    """
    signature = hmac.new(app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    return f"sha256={signature}"


def is_request_expired(timestamp: str, max_age_seconds: int = 300) -> bool:
    """
    Check if a webhook request is too old (potential replay attack)

    Args:
        timestamp: The timestamp from the webhook payload
        max_age_seconds: Maximum allowed age in seconds

    Returns:
        bool: True if request is expired, False otherwise
    """
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        age = current_time - request_time

        return age > max_age_seconds
    except (ValueError, TypeError):
        # If timestamp is invalid, consider request as expired
        return True
