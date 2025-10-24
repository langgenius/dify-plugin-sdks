# Twilio Trigger Plugin for Dify

Trigger Dify workflows via Twilio webhooks for SMS, voice calls, and WhatsApp messages.

## Features

### 📱 SMS Events (2 events)
- **SMS Incoming** (`sms_incoming`) - Receive SMS/MMS messages
- **SMS Status** (`sms_status`) - SMS delivery status callbacks (queued/sending/sent/delivered/undelivered/failed)

### 📞 Voice Call Events (5 events)
- **Voice Incoming** (`voice_incoming`) - Receive incoming calls (inbound only)
- **Voice Initiated** (`voice_initiated`) - Call initiated/queued (queued/initiated)
- **Voice Ringing** (`voice_ringing`) - Call ringing
- **Voice Answered** (`voice_answered`) - Call answered (in-progress/answered)
- **Voice Completed** (`voice_completed`) - Call ended (completed/busy/no-answer/canceled/failed)
- **Recording Completed** (`recording_completed`) - Call recording finished

### 💬 WhatsApp Events (2 events)
- **WhatsApp Incoming** (`whatsapp_incoming`) - Receive WhatsApp messages
- **WhatsApp Status** (`whatsapp_status`) - WhatsApp delivery status callbacks (queued/sent/delivered/read/failed)

**Total: 10 events**

## Prerequisites

1. **Twilio Account**
   - Sign up at [twilio.com](https://www.twilio.com)
   - Get your Account SID and Auth Token from the [Console](https://console.twilio.com)
   - Purchase or configure a Twilio phone number

2. **Dify Instance**
   - Dify version 1.10.0 or higher
   - Public webhook endpoint (for receiving Twilio webhooks)

## Quick Start

### 1. Get Twilio Credentials

1. Log in to [Twilio Console](https://console.twilio.com)
2. Copy your **Account SID** (starts with `AC`)
3. Copy your **Auth Token** (click "Show" to reveal)

### 2. Install Plugin

In Dify:
1. Go to **Plugins** → **Triggers**
2. Search for "Twilio"
3. Click **Install**

### 3. Configure Credentials

**Option A: API Key Authentication** (Simpler)

1. Click on the Twilio plugin
2. Select **API Key** authentication
3. Enter credentials:
   - **Account SID**: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **Auth Token**: Your auth token from Twilio Console

**Option B: OAuth Authentication** (More Secure)

1. Create OAuth App in [Twilio Console](https://www.twilio.com/console/oauth/apps)
   - App Name: Your app name
   - Redirect URI: Provided by Dify
   - Scopes: `openid profile email`
2. Copy **Client ID** and **Client Secret**
3. In Dify, select **OAuth** authentication
4. Enter Client ID and Client Secret
5. Click **Authorize**
6. Complete OAuth flow

📖 See [API_KEY_REQUIREMENTS.md](API_KEY_REQUIREMENTS.md) for API Key setup guide.

### 4. Create Subscription

1. **Select Phone Number**: Choose from your Twilio numbers
2. **Select Events**: Choose which events to monitor
3. Click **Create**

The plugin automatically configures webhooks on your Twilio phone number!

### 5. ⚠️ Configure Voice Status Events (IMPORTANT!)

**If you selected any Voice status events** (`voice_initiated`, `voice_ringing`, `voice_answered`, `voice_completed`), you MUST manually enable them in Twilio Console:

1. Go to [Twilio Phone Numbers](https://www.twilio.com/console/phone-numbers/incoming)
2. Select your phone number
3. Scroll to **CALL STATUS CHANGES** section
4. The Status Callback URL is already set by the plugin
5. **Check these boxes** (this is the required manual step):
   - ☑ **Initiated** (enables `voice_initiated` event)
   - ☑ **Ringing** (enables `voice_ringing` event)
   - ☑ **Answered** (enables `voice_answered` event)
   - ☑ **Completed** (enables `voice_completed` event)
6. Click **Save**

**Why is this manual step required?**

Twilio's `IncomingPhoneNumber.update()` API does not support the `status_callback_event` parameter. This parameter is only available when creating individual outbound calls via the Call API or in TwiML. For phone number configuration, you must manually enable these events in the console.

📖 See [VOICE_WEBHOOK_SETUP.md](VOICE_WEBHOOK_SETUP.md) for detailed configuration guide.

---

## Documentation

- **[VOICE_EVENTS.md](VOICE_EVENTS.md)** - Detailed Voice events documentation
- **[VOICE_WEBHOOK_SETUP.md](VOICE_WEBHOOK_SETUP.md)** - Voice webhook configuration guide
- **[API_KEY_REQUIREMENTS.md](API_KEY_REQUIREMENTS.md)** - API Key requirements and setup
- **[EVENTS_SUMMARY.md](EVENTS_SUMMARY.md)** - Complete events reference (Chinese)

---

## Quick Event Reference

### SMS Events

#### sms_incoming
- **Trigger**: Incoming SMS/MMS received
- **Filters**: `from_number`, `to_number`, `body_contains`, `has_media`
- **Use Cases**: Auto-reply, keyword processing, customer support

#### sms_status
- **Trigger**: Outbound SMS status change
- **Filters**: `status_filter`, `to_number`, `error_code_filter`
- **Statuses**: queued → sending → sent → delivered/undelivered/failed

### Voice Events

#### voice_incoming
- **Trigger**: Incoming call received (inbound only)
- **Filters**: `from_number`, `to_number`
- **Use Cases**: Call routing, caller ID screening, IVR

#### voice_initiated
- **Trigger**: Outbound call queued/initiated
- **Filters**: `from_number`, `to_number`, `direction_filter`
- **Statuses**: queued, initiated

#### voice_ringing
- **Trigger**: Call ringing (before answer)
- **Filters**: `from_number`, `to_number`, `direction_filter`
- **Use Cases**: Pre-answer processing, analytics

#### voice_answered
- **Trigger**: Call answered/in-progress
- **Filters**: `from_number`, `to_number`, `direction_filter`
- **Statuses**: in-progress, answered
- **Use Cases**: Start recording, CRM updates

#### voice_completed
- **Trigger**: Call ended
- **Filters**: `from_number`, `to_number`, `direction_filter`, `min_duration`, `max_duration`
- **Statuses**: completed, busy, no-answer, canceled, failed
- **Additional Data**: Duration, Price, ErrorCode
- **Use Cases**: Call logging, billing, analytics

### WhatsApp Events

#### whatsapp_incoming
- **Trigger**: Incoming WhatsApp message
- **Filters**: `from_number`, `to_number`, `body_contains`, `has_media`
- **Use Cases**: Customer support, chatbots

#### whatsapp_status
- **Trigger**: Outbound WhatsApp status change
- **Filters**: `status_filter`, `to_number`
- **Statuses**: queued → sent → delivered → read/failed
- **Note**: Read receipts only if recipient has them enabled

---

## Authentication Methods

| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| **Auth Token** | Development/Testing | Simple setup | Full account access |
| **API Keys (Main type)** | Production | Revocable, scoped | Must be "Main" type |
| **OAuth** | Multi-tenant SaaS | User authorization | Complex setup |

⚠️ **Important for API Keys**: You MUST use "Main" type API Keys. "Standard" and "Restricted" types cannot access the `/Accounts` endpoint and will fail validation. See [API_KEY_REQUIREMENTS.md](API_KEY_REQUIREMENTS.md).

---

## Common Issues

### Q: I only receive `voice_incoming` events, not other voice events?

**A**: You must manually check the "Call Status Changes" boxes in Twilio Console. See [Step 5](#5-️-configure-voice-status-events-important) above.

### Q: API Key validation fails with HTTP 401?

**A**: You likely created a "Standard" or "Restricted" API Key. You MUST use "Main" type. See [API_KEY_REQUIREMENTS.md](API_KEY_REQUIREMENTS.md).

### Q: What's the difference between SMS and MMS?

**A**: SMS is text-only, MMS includes media (images, videos). Both use the same event (`sms_incoming`), differentiated by `NumMedia` field (0=SMS, >0=MMS).

### Q: WhatsApp 24-hour window restriction?

**A**: Yes. After 24 hours of no user message, you can only send pre-approved template messages. See [Twilio WhatsApp docs](https://www.twilio.com/docs/whatsapp).

---

## Development

### Run Tests

```bash
cd python/examples/twilio_trigger
source .venv/bin/activate
pytest tests/
```

### Test Credentials

```bash
python test_credentials.py
```

### Local Run

```bash
python main.py
```

---

## File Structure

```
twilio_trigger/
├── events/                    # Event handlers
│   ├── sms_incoming/         # SMS receiving
│   ├── sms_status/           # SMS status
│   ├── voice_incoming/       # Incoming calls
│   ├── voice_initiated/      # Call initiated
│   ├── voice_ringing/        # Call ringing
│   ├── voice_answered/       # Call answered
│   ├── voice_completed/      # Call completed
│   ├── whatsapp_incoming/    # WhatsApp receiving
│   ├── whatsapp_status/      # WhatsApp status
│   ├── recording_completed/  # Recording finished
│   └── utils/                # Utility functions
├── provider/
│   ├── twilio.yaml          # Provider config
│   └── twilio.py            # Provider implementation
├── manifest.yaml            # Plugin manifest
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
└── tests/                   # Test files
```

---

## Version Info

- **Plugin Version**: 0.0.1
- **SDK Version**: 0.6.0b13
- **Twilio SDK**: twilio~=9.0
- **Python**: 3.12+

---

## Links

- [Twilio Console](https://www.twilio.com/console)
- [Twilio Phone Numbers](https://www.twilio.com/console/phone-numbers/incoming)
- [Twilio API Keys](https://www.twilio.com/console/project/api-keys)
- [Twilio Messaging Webhooks](https://www.twilio.com/docs/usage/webhooks/messaging-webhooks)
- [Twilio Voice Webhooks](https://www.twilio.com/docs/usage/webhooks/voice-webhooks)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)

---

## License

See [LICENSE](../../LICENSE) file

---

**Last Updated**: 2025-01-28
