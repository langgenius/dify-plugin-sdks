# Google Drive Trigger Example

This example Trigger plugin demonstrates how to automatically subscribe to Google Drive
change notifications using the Drive v3 API. It provisions a webhook channel through
OAuth, validates incoming notification headers, and transforms change feed entries into
workflow variables.

## Features

- OAuth-based subscription constructor that issues a `changes.watch` request and stores
  the generated channel metadata (channel ID, resource ID, expiration, verification token).
- Trigger implementation that validates Google-signed headers (`X-Goog-*`) and ignores
  sync handshakes.
- Event handler that fetches the Drive change feed, persists the most recent
  `startPageToken`, and exposes structured information about each change to workflows.
- Optional filters to include removed items, restrict to "My Drive", and tune the number
  of changes fetched per notification.

## Setup

1. Create a Google Cloud project with the **Google Drive API** enabled.
2. Configure an OAuth client (type **Web application**) and add the Dify callback URL as
   an authorized redirect URI.
3. Copy the OAuth client ID and secret into the plugin provider configuration in Dify.
4. Deploy this plugin and add the **Google Drive Change Detected** trigger to your
   workflow.
5. Authenticate with Google Drive via OAuth and select the Drive spaces you want to
   monitor. The constructor will start a new watch channel automatically.

## Testing

Compile-time validation ensures the module imports cleanly:

```bash
python -m compileall python/examples/google_drive_trigger
```

### Attention

- Enable the **Google Drive API** in the Google Cloud Console.
