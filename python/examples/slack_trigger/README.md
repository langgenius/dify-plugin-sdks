# Slack Trigger Plugin

This example plugin demonstrates how to build Slack webhook triggers for Dify workflows.
It validates Slack signatures, handles URL verification requests, and dispatches events
for the full Slack Events API catalog covering messages, reactions, workspace administration
changes, files, user groups, and more.

## Features

- **Signature Validation** – Uses Slack signing secrets to verify webhook authenticity.
- **URL Verification** – Automatically responds to Slack's `url_verification` challenge.
- **Retry Awareness** – Ignores Slack retry deliveries while acknowledging the request.
- **Rich Event Payloads** – Normalises Slack event envelopes into workflow-friendly variables with defaults instead of nulls.
- **Comprehensive Coverage** – Auto-generates transformers for every event listed in the [Slack Events API reference](https://docs.slack.dev/reference/events) by reading Slack's published specification.

## Setup

1. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create a Slack App and enable Event Subscriptions.
   - Set the Request URL to the webhook endpoint provided by Dify after installing the plugin.
   - Add the event types you want to subscribe to. The plugin exposes every event documented at [https://docs.slack.dev/reference/events](https://docs.slack.dev/reference/events), so enable the ones relevant to your workflow inside the Slack app configuration.

3. Copy the app **Signing Secret** from your Slack App's **Basic Information** page.

4. When you configure the trigger inside Dify, provide:
   - The Slack workspace/team ID (e.g. `T0123456789`).
   - The signing secret you copied above.

   Event subscriptions remain managed inside the Slack app configuration, so Dify only needs the workspace identifier and signing secret.

## Available Events

All event transformers are generated from Slack's official Events API specification (`slack_events_api_async_v1.json`). Each
event YAML references the same catalog-driven Python transformer, so new events in the specification can be incorporated by
re-running the generation script if Slack adds more entries.

The following categories are included:

- **App lifecycle** – `app_mention`, `app_rate_limited`, `app_uninstalled`.
- **Channels & groups** – `channel_*`, `group_*`, `member_joined_channel`, `member_left_channel`.
- **Direct messages** – `im_*`, `message_im`, `message_mpim`.
- **Messages** – `message`, `message_channels`, `message_groups`, `message_app_home`.
- **Files & pins** – `file_*`, `pin_added`, `pin_removed`.
- **Reactions & stars** – `reaction_added`, `reaction_removed`, `star_added`, `star_removed`.
- **Workspace admin** – `team_domain_change`, `team_join`, `team_rename`, `tokens_revoked`, `scope_*`, `resources_*`.
- **User groups & DND** – `subteam_*`, `dnd_updated`, `dnd_updated_user`.
- **Miscellaneous** – `link_shared`, `grid_migration_*`, `email_domain_changed`, `emoji_changed`, `user_change`.

Each event description in the manifest links back to the authoritative Slack documentation so you can confirm payload formats
before building automations.

## Usage

1. Install and configure the plugin inside Dify.
2. Add one of the Slack triggers to your workflow and adjust the per-event parameters.
3. Deploy the workflow; Slack events will now invoke your automation.
