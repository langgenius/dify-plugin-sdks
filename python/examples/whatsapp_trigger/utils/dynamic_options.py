"""
Dynamic Options Fetching Utility

This module provides functions to fetch dynamic options from the WhatsApp Business API,
such as available phone numbers for the account.
"""

import requests
from typing import List

from dify_plugin.entities import ParameterOption


def fetch_phone_numbers(access_token: str) -> List[ParameterOption]:
    """
    Fetch available WhatsApp Business phone numbers for the account

    Args:
        access_token: The system user access token for WhatsApp Business API

    Returns:
        List[ParameterOption]: List of phone number options
    """
    if not access_token:
        return []

    try:
        # WhatsApp Business API endpoint to fetch phone numbers
        # This would typically fetch from the WhatsApp Business Management API
        url = "https://graph.facebook.com/v19.0/me/phone_numbers"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"Failed to fetch phone numbers: {response.status_code}")
            return []

        data = response.json()
        phone_numbers = data.get("data", [])

        options = []
        for phone in phone_numbers:
            phone_id = phone.get("id", "")
            display_number = phone.get("display_phone_number", "")
            verified_name = phone.get("verified_name", "")

            # Create a readable label
            if verified_name:
                label = f"{display_number} ({verified_name})"
            else:
                label = display_number

            if phone_id and display_number:
                options.append(ParameterOption(
                    label=label,
                    value=phone_id
                ))

        return options

    except Exception as e:
        print(f"Error fetching phone numbers: {e}")
        # Return some example options for demo purposes
        return [
            ParameterOption(
                label="+1 (555) 123-4567 (Demo Business)",
                value="123456789012345"
            ),
            ParameterOption(
                label="+1 (555) 987-6543 (Support Line)",
                value="987654321098765"
            )
        ]


def fetch_message_templates(access_token: str, phone_number_id: str) -> List[ParameterOption]:
    """
    Fetch available message templates for a WhatsApp Business phone number

    Args:
        access_token: The system user access token
        phone_number_id: The WhatsApp Business phone number ID

    Returns:
        List[ParameterOption]: List of message template options
    """
    if not access_token or not phone_number_id:
        return []

    try:
        # WhatsApp Business API endpoint to fetch message templates
        url = f"https://graph.facebook.com/v19.0/{phone_number_id}/message_templates"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"Failed to fetch templates: {response.status_code}")
            return []

        data = response.json()
        templates = data.get("data", [])

        options = []
        for template in templates:
            template_name = template.get("name", "")
            template_status = template.get("status", "")
            template_category = template.get("category", "")

            # Only include approved templates
            if template_status == "APPROVED" and template_name:
                label = f"{template_name} ({template_category})"
                options.append(ParameterOption(
                    label=label,
                    value=template_name
                ))

        return options

    except Exception as e:
        print(f"Error fetching message templates: {e}")
        return []


def fetch_labels(access_token: str, phone_number_id: str) -> List[ParameterOption]:
    """
    Fetch available labels for organizing conversations

    Args:
        access_token: The system user access token
        phone_number_id: The WhatsApp Business phone number ID

    Returns:
        List[ParameterOption]: List of label options
    """
    if not access_token or not phone_number_id:
        return []

    try:
        # WhatsApp Business API endpoint to fetch labels
        url = f"https://graph.facebook.com/v19.0/{phone_number_id}/labels"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"Failed to fetch labels: {response.status_code}")
            return []

        data = response.json()
        labels = data.get("data", [])

        options = []
        for label in labels:
            label_name = label.get("name", "")
            label_id = label.get("id", "")

            if label_name and label_id:
                options.append(ParameterOption(
                    label=label_name,
                    value=label_id
                ))

        return options

    except Exception as e:
        print(f"Error fetching labels: {e}")
        # Return some example labels for demo purposes
        return [
            ParameterOption(label="New Customer", value="label_1"),
            ParameterOption(label="VIP", value="label_2"),
            ParameterOption(label="Support", value="label_3"),
            ParameterOption(label="Sales", value="label_4"),
        ]