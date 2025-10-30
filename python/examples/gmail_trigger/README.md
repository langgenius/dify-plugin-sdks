Gmail Trigger (Push + History)

Overview
- Gmail Trigger is a Dify provider that receives Gmail push notifications via Cloud Pub/Sub and emits concrete events based on Gmail History:
  - `gmail_message_added` (new messages)
  - `gmail_message_deleted` (deleted messages)
  - `gmail_label_added` (labels added to messages)
  - `gmail_label_removed` (labels removed from messages)
- Dispatch verifies/auths the push, pulls the history delta once, and splits changes for events to consume.
- Note: API Key is NOT supported for Gmail API access. Use OAuth (gmail.readonly) only.

Prerequisites
- A Google account authorized for Gmail API (used during OAuth)
- A Google Cloud project with Pub/Sub enabled (manual setup)

Step-by-step Setup
1) Install the plugin in Dify
- Options:
  - If packaged as `.difypkg`, import it in Dify’s Plugin Center (Plugins → Import).
  - For local run during development, ensure the runtime installs dependencies in `requirements.txt`.

2) Configure OAuth in the provider (one-time)
- In Google Cloud Console → APIs & Services → Credentials → Create Credentials → OAuth client ID
  - Application type: Web application
  - Authorized redirect URIs: Copy the redirect URI shown by Dify when setting up OAuth for this provider
- Back in Dify, enter Client ID/Secret; click “Authorize” to complete OAuth (gmail.readonly)
- The constructor validates the token via `users/me/profile`

3) Create a Gmail subscription in Dify
- Parameters
  - `watch_email` (userId): use `me` or the full Gmail address
  - `topic_name`: Paste the full Pub/Sub topic path you created (e.g., `projects/<PROJECT_ID>/topics/<TOPIC>`). If you configure tenant-level GCP client params (see below), you may leave this empty and the plugin will auto-provision Pub/Sub.
  - `label_ids` (optional): scope to specific labels (INBOX/UNREAD...)
    - Docs: https://developers.google.com/gmail/api/reference/rest/v1/users.labels/list
  - `label_filter_action` (optional): `include` or `exclude` for users.watch
    - Docs: https://developers.google.com/gmail/api/reference/rest/v1/users/watch#request-body
  - Properties (optional)
    - `require_oidc`: enforce OIDC bearer verification
    - `oidc_audience`: use the exact webhook endpoint URL (shown after subscription is created)
    - `oidc_service_account_email`: the service account used by the Pub/Sub push subscription
- After you click Create, open the subscription details and copy the Webhook Endpoint URL. You will use this in Pub/Sub push.

4) Prepare Pub/Sub (manual)
   - Enable APIs:
     - Gmail API: https://console.cloud.google.com/apis/library/gmail.googleapis.com
     - Cloud Pub/Sub API: https://console.cloud.google.com/apis/library/pubsub.googleapis.com
   - Create topic:
     - `gcloud pubsub topics create <TOPIC> --project=<PROJECT_ID>`
   - Grant Gmail publisher on the topic:
     - `gcloud pubsub topics add-iam-policy-binding projects/<PROJECT_ID>/topics/<TOPIC> \
        --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
        --role=roles/pubsub.publisher`
   - Create a Push subscription to the Callback URL displayed by Dify:
     - `gcloud pubsub subscriptions create <SUB_NAME> \
        --topic=projects/<PROJECT_ID>/topics/<TOPIC> \
        --push-endpoint="https://<YOUR_DIFY_HOST>/api/plugin/triggers/<SUBSCRIPTION_ID>"`
     - OIDC (optional): add `--push-auth-service-account=<YOUR_SA_EMAIL>` and `--push-auth-token-audience="<Callback URL>"`

Auto mode (tenant-level)
- Configure in OAuth client params (one-time, tenant-level):
  - `gcp_project_id`: GCP project ID
  - `gcp_service_account_json`: Service Account JSON with Pub/Sub admin perms
  - Optional `gcp_topic_id`: default to `dify-gmail`
- With these set, if `topic_name` is empty, the plugin will:
  - Create/reuse Topic and grant Gmail publisher
  - Create a dedicated Push subscription per Dify subscription (supports OIDC)
  - Call `users.watch` with the managed Topic
- On unsubscribe, the plugin will best-effort delete the managed Push subscription (Topic is preserved for reuse).

Where To Get OIDC Values
- `oidc_audience`
  - Use the exact webhook endpoint URL shown in the Dify subscription details (Endpoint). Example:
    - `https://<your-dify-host>/api/plugin/triggers/<subscription-id>`
  - The YAML field includes a URL to Google docs for the `audience` claim: see the OIDC token reference.
- `oidc_service_account_email`
  - The service account used by the Pub/Sub push subscription (set via `--push-auth-service-account`).
  - Find it under Google Cloud Console → IAM & Admin → Service Accounts, or via:
    - `gcloud iam service-accounts list --format='value(email)'`
  - The YAML field links to the Service Accounts console page.

How It Works
- Dispatch (trigger)
  - Optionally verifies OIDC bearer from Pub/Sub push (iss/aud/email)
  - Decodes `message.data` to get `historyId`/`emailAddress`
  - Calls `users.history.list(startHistoryId=...)` once to gather deltas
  - Splits changes per family and stores pending batches in Dify storage
  - Returns the list of concrete event names for Dify to execute
- Events
  - Read the pending batch for their family
  - `gmail_message_added` fetches full message metadata (headers, attachments meta)
  - Output matches the event YAML `output_schema`

Event Outputs (high-level)
- `gmail_message_added`
  - `history_id`: string
  - `messages[]`: id, threadId, internalDate, snippet, sizeEstimate, labelIds, headers{From,To,Subject,Date,Message-Id}, has_attachments, attachments[]
- `gmail_message_deleted`
  - `history_id`: string
  - `messages[]`: id, threadId
- `gmail_label_added` / `gmail_label_removed`
  - `history_id`: string
  - `changes[]`: id, threadId, labelIds

Lifecycle & Refresh
- Create: `users.watch` with `topicName`, optional `labelIds`/`labelFilterAction`
- Refresh: `users.watch` again before expiry (Gmail watch is time-limited). If `expiration` not provided, plugin targets ~6 days
- Delete: `users.stop`

Testing
- Send an email to the watched mailbox (INBOX). You should see `gmail_message_added`
- Mark read/unread (UNREAD label removed/added) triggers label events
- Delete an email triggers `gmail_message_deleted`
 - Tip: You can view recent deliveries in Pub/Sub subscription details; Dify logs/console will show trigger and event traces.

Troubleshooting
- Nothing triggers: ensure topic exists, Gmail has publisher role on the topic, and push subscription points to Dify endpoint
- 401/403 at dispatch: OIDC settings mismatch; verify service account and audience
- `historyId` out of date: plugin resets checkpoint to the latest notification and skips the batch
- OAuth issues: re-authorize the provider; token is validated by `users/me/profile`

References
- Gmail Push: https://developers.google.com/workspace/gmail/api/guides/push
- History: https://developers.google.com/gmail/api/reference/rest/v1/users.history/list
- Messages: https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get
