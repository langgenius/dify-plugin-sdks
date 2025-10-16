# Gmail Trigger (Automatic Subscription)

This example trigger plugin demonstrates how to automatically create and manage [Gmail push notifications](https://developers.google.com/gmail/api/guides/push) for Dify workflows.
It authenticates with Gmail via OAuth, registers a Gmail `watch`, and processes Pub/Sub push payloads so that new mailbox activity can launch a workflow without any manual webhook wiring.

## Features

- **Automatic watch provisioning** – Uses the Gmail API to subscribe the authenticated mailbox to a Google Cloud Pub/Sub topic.
- **Pub/Sub push validation** – Supports optional verification tokens to ensure that only trusted Pub/Sub deliveries are processed.
- **History-aware event transformation** – Retrieves Gmail history entries, tracks the last processed `historyId`, and (optionally) fetches message payloads for each change.
- **Token lifecycle management** – Implements the full OAuth flow, including token refresh handling.

## Prerequisites

1. A Google Cloud project with the Gmail API enabled.
2. A Pub/Sub topic and push subscription that forwards events to the Dify callback URL.
   - If you use the verification token option, configure the same token on the Pub/Sub subscription.
3. An OAuth client (type *Web application*) with the Dify redirect URI added to the authorized redirect URIs list.

## Configuration overview

- **Provider (`provider/gmail.yaml`)**
  - Declares constructor parameters for the Pub/Sub topic, optional label filters, and verification token.
  - Configures OAuth client/credential schemas for Google.
  - Registers the trigger implementation class in `provider/gmail.py`.
- **Trigger implementation (`provider/gmail.py`)**
  - Validates Pub/Sub requests, decodes the envelope, and dispatches the `gmail_new_email` event.
  - Creates, refreshes, and deletes Gmail `watch` subscriptions using the authenticated mailbox.
- **Event implementation (`events/new_email`)**
  - Converts Gmail history notifications into workflow variables, fetching message payloads if requested.
  - Persists the last `historyId` per subscription using the plugin storage channel.

## Running the example

```bash
cd python/examples/gmail_trigger
pdm install  # or `pip install -r requirements.txt`
pdm run python main.py
```

Deploy the built plugin to your Dify instance, complete the OAuth authorization, provide your Pub/Sub topic, and start building workflows that react to Gmail events instantly.
