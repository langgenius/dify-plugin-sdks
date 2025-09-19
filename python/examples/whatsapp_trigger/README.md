# WhatsApp Business Trigger Plugin

A Dify plugin that integrates WhatsApp Business Platform webhooks to trigger workflows based on WhatsApp messages and events.

## Features

### 🎯 Supported Triggers

#### Message Events
- **Text Messages**: Trigger workflows when text messages are received
- **Image Messages**: Handle image uploads with captions
- **Message Status Updates**: Track delivery, read receipts, and failures

#### Advanced Filtering
- Filter by keywords, sender, language
- Message length and caption filtering
- Conversation context awareness

#### Security
- HMAC-SHA256 signature validation
- Replay attack protection
- Sensitive data filtering

## Setup Instructions

### 1. Prerequisites

- WhatsApp Business Account
- Meta Business Verification
- System User Access Token with required permissions
- App Secret from Meta App Dashboard

### 2. Installation

1. Deploy the plugin to your Dify instance
2. Configure credentials in Dify:
   - System Access Token
   - App Secret

### 3. Webhook Configuration

1. In Meta App Dashboard, go to WhatsApp > Configuration
2. Add webhook URL: `https://your-dify-instance.com/api/plugins/whatsapp_trigger/webhook`
3. Set Verify Token (will be provided by the plugin)
4. Subscribe to webhook fields:
   - `messages`
   - `message_status`
   - `messaging_product`

### 4. Create a Workflow

1. Create a new workflow in Dify
2. Add WhatsApp trigger node
3. Select trigger type (e.g., `message_text`)
4. Configure filters as needed
5. Build your automation flow

## Example Use Cases

### Customer Support Automation
```yaml
Trigger: message_text
Filter: keyword_filter: "help, support, issue"
Actions:
  - Create support ticket
  - Send acknowledgment message
  - Route to appropriate team
```

### Order Processing
```yaml
Trigger: message_text
Filter: keyword_filter: "order, buy, purchase"
Actions:
  - Extract order details
  - Check inventory
  - Process payment
  - Send confirmation
```

### Media Processing
```yaml
Trigger: message_image
Filter: has_caption: "yes"
Actions:
  - Download image
  - Analyze with AI
  - Store in database
  - Send response
```

## Architecture

```
whatsapp_trigger/
├── provider/
│   ├── whatsapp.yaml    # Provider configuration
│   └── whatsapp.py      # Core webhook handling
├── triggers/
│   ├── message_*.yaml   # Trigger definitions
│   └── message_*.py     # Trigger implementations
└── utils/
    ├── signature_validator.py  # Security utilities
    └── dynamic_options.py      # API integrations
```

## Security Considerations

1. **Always use HTTPS** for webhook endpoints
2. **Validate signatures** on all incoming requests
3. **Store credentials securely** in Dify's credential manager
4. **Implement rate limiting** to prevent abuse
5. **Monitor webhook logs** for suspicious activity

## Troubleshooting

### Common Issues

1. **Webhook not receiving events**
   - Check webhook URL is accessible
   - Verify token matches configuration
   - Ensure webhook is subscribed to correct fields

2. **Signature validation failing**
   - Verify App Secret is correct
   - Check system time synchronization
   - Ensure raw body is used for validation

3. **Missing message data**
   - Check API permissions
   - Verify phone number is registered
   - Ensure webhook version is compatible

## Contributing

To extend this plugin with new triggers:

1. Create trigger definition in `triggers/[name].yaml`
2. Implement trigger logic in `triggers/[name].py`
3. Add trigger to `provider/whatsapp.yaml`
4. Test with sample webhook payloads

## License

This plugin is part of the Dify Plugin SDK examples and follows the same license terms.