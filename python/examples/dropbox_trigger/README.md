Dropbox Trigger (Manual Webhook)

Overview
- Manual webhook trigger: users create their own Dropbox App and set the App's Webhook URL directly to this subscription endpoint.
- The trigger validates signatures and emits `file_changes` that includes the notified account IDs and resolved change entries from the entire Dropbox account.

Webhook Validation
- GET challenge echo: returns the `challenge` query parameter verbatim.
- Signature: verify `X-Dropbox-Signature` via HMAC-SHA256 of the raw body using your Dropbox App Secret.

Subscription
- Parameters:
  - `app_secret` (required): used to validate webhook signatures.
  - `access_token` (required): user access token to fetch file change details.
- Steps:
  1) In Dropbox App Console → your app → Settings → Webhooks, set the Webhook URL to: `https://<your-dify-host>/api/plugin/triggers/<subscription-id>`
  2) In Dify subscription UI, paste the App Secret and Access Token.

Dispatch Flow
1) Webhook arrives (POST). Validate signature.
2) Extract `list_folder.accounts` from payload (if present).
3) Fetch file changes recursively from entire Dropbox account (including deleted files).
4) Emit `file_changes` with `{ accounts, cursor_before, cursor_after, changes, raw, headers, received_at }`.

Files
- `provider/dropbox.py`: trigger dispatch (manual webhook)
- `provider/dropbox.yaml`: provider identity, schemas, and event registration
- `events/file_changes/file_changes.yaml`: event identity and output schema (name: `file_changes`)

Notes
- The trigger monitors the entire Dropbox account recursively, including deleted files.
- Change cursor is stored to track incremental updates between webhook notifications.
