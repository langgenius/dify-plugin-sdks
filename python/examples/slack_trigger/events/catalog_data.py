"""Auto-generated Slack event catalog from Slack Events API spec."""

from __future__ import annotations

EVENT_CATALOG: dict[str, dict[str, object]] = {
  "app_mention": {
    "topic": "app.mention",
    "summary": "Subscribe to only the message events that mention your app or bot",
    "doc_url": "https://api.slack.com/events/app_mention",
    "scopes_required": [],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens",
      "app_event"
    ],
    "category": "app",
    "label": "App Mention",
    "event_type": "app_mention"
  },
  "app_rate_limited": {
    "topic": "app.rate.limited",
    "summary": "Indicates your app's event subscriptions are being rate limited",
    "doc_url": "https://api.slack.com/events/app_rate_limited",
    "scopes_required": [],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "app_event",
      "allows_workspace_tokens"
    ],
    "category": "app",
    "label": "App Rate Limited",
    "event_type": "app_rate_limited"
  },
  "app_uninstalled": {
    "topic": "app.uninstalled",
    "summary": "Your Slack app was uninstalled.",
    "doc_url": "https://api.slack.com/events/app_uninstalled",
    "scopes_required": [],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "app_event",
      "allows_workspace_tokens"
    ],
    "category": "app",
    "label": "App Uninstalled",
    "event_type": "app_uninstalled"
  },
  "channel_archive": {
    "topic": "channel.archive",
    "summary": "A channel was archived",
    "doc_url": "https://api.slack.com/events/channel_archive",
    "scopes_required": [
      "channels:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "channel",
    "label": "Channel Archive",
    "event_type": "channel_archive"
  },
  "channel_created": {
    "topic": "channel.created",
    "summary": "A channel was created",
    "doc_url": "https://api.slack.com/events/channel_created",
    "scopes_required": [
      "channels:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "channel",
    "label": "Channel Created",
    "event_type": "channel_created"
  },
  "channel_deleted": {
    "topic": "channel.deleted",
    "summary": "A channel was deleted",
    "doc_url": "https://api.slack.com/events/channel_deleted",
    "scopes_required": [
      "channels:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "channel",
    "label": "Channel Deleted",
    "event_type": "channel_deleted"
  },
  "channel_history_changed": {
    "topic": "channel.history.changed",
    "summary": "Bulk updates were made to a channel's history",
    "doc_url": "https://api.slack.com/events/channel_history_changed",
    "scopes_required": [
      "channels:history",
      "groups:history",
      "mpim:history"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "channel",
    "label": "Channel History Changed",
    "event_type": "channel_history_changed"
  },
  "channel_left": {
    "topic": "channel.left",
    "summary": "You left a channel",
    "doc_url": "https://api.slack.com/events/channel_left",
    "scopes_required": [
      "channels:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "channel",
    "label": "Channel Left",
    "event_type": "channel_left"
  },
  "channel_rename": {
    "topic": "channel.rename",
    "summary": "A channel was renamed",
    "doc_url": "https://api.slack.com/events/channel_rename",
    "scopes_required": [
      "channels:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "channel",
    "label": "Channel Rename",
    "event_type": "channel_rename"
  },
  "channel_unarchive": {
    "topic": "channel.unarchive",
    "summary": "A channel was unarchived",
    "doc_url": "https://api.slack.com/events/channel_unarchive",
    "scopes_required": [
      "channels:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "channel",
    "label": "Channel Unarchive",
    "event_type": "channel_unarchive"
  },
  "dnd_updated": {
    "topic": "dnd.updated",
    "summary": "Do not Disturb settings changed for the current user",
    "doc_url": "https://api.slack.com/events/dnd_updated",
    "scopes_required": [
      "dnd:read"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "dnd",
    "label": "DND Updated",
    "event_type": "dnd_updated"
  },
  "dnd_updated_user": {
    "topic": "dnd.updated.user",
    "summary": "Do not Disturb settings changed for a member",
    "doc_url": "https://api.slack.com/events/dnd_updated_user",
    "scopes_required": [
      "dnd:read"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "dnd",
    "label": "DND Updated User",
    "event_type": "dnd_updated_user"
  },
  "email_domain_changed": {
    "topic": "email.domain.changed",
    "summary": "The workspace email domain has changed",
    "doc_url": "https://api.slack.com/events/email_domain_changed",
    "scopes_required": [
      "team:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "email",
    "label": "Email Domain Changed",
    "event_type": "email_domain_changed"
  },
  "emoji_changed": {
    "topic": "emoji.changed",
    "summary": "A custom emoji has been added or changed",
    "doc_url": "https://api.slack.com/events/emoji_changed",
    "scopes_required": [
      "emoji:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "emoji",
    "label": "Emoji Changed",
    "event_type": "emoji_changed"
  },
  "file_change": {
    "topic": "file.change",
    "summary": "A file was changed",
    "doc_url": "https://api.slack.com/events/file_change",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Change",
    "event_type": "file_change"
  },
  "file_comment_added": {
    "topic": "file.comment.added",
    "summary": "A file comment was added",
    "doc_url": "https://api.slack.com/events/file_comment_added",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Comment Added",
    "event_type": "file_comment_added"
  },
  "file_comment_deleted": {
    "topic": "file.comment.deleted",
    "summary": "A file comment was deleted",
    "doc_url": "https://api.slack.com/events/file_comment_deleted",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Comment Deleted",
    "event_type": "file_comment_deleted"
  },
  "file_comment_edited": {
    "topic": "file.comment.edited",
    "summary": "A file comment was edited",
    "doc_url": "https://api.slack.com/events/file_comment_edited",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Comment Edited",
    "event_type": "file_comment_edited"
  },
  "file_created": {
    "topic": "file.created",
    "summary": "A file was created",
    "doc_url": "https://api.slack.com/events/file_created",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Created",
    "event_type": "file_created"
  },
  "file_deleted": {
    "topic": "file.deleted",
    "summary": "A file was deleted",
    "doc_url": "https://api.slack.com/events/file_deleted",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Deleted",
    "event_type": "file_deleted"
  },
  "file_public": {
    "topic": "file.public",
    "summary": "A file was made public",
    "doc_url": "https://api.slack.com/events/file_public",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Public",
    "event_type": "file_public"
  },
  "file_shared": {
    "topic": "file.shared",
    "summary": "A file was shared",
    "doc_url": "https://api.slack.com/events/file_shared",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Shared",
    "event_type": "file_shared"
  },
  "file_unshared": {
    "topic": "file.unshared",
    "summary": "A file was unshared",
    "doc_url": "https://api.slack.com/events/file_unshared",
    "scopes_required": [
      "files:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "file",
    "label": "File Unshared",
    "event_type": "file_unshared"
  },
  "grid_migration_finished": {
    "topic": "grid.migration.finished",
    "summary": "An enterprise grid migration has finished on this workspace.",
    "doc_url": "https://api.slack.com/events/grid_migration_finished",
    "scopes_required": [],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "app_event",
      "allows_workspace_tokens"
    ],
    "category": "grid",
    "label": "Grid Migration Finished",
    "event_type": "grid_migration_finished"
  },
  "grid_migration_started": {
    "topic": "grid.migration.started",
    "summary": "An enterprise grid migration has started on this workspace.",
    "doc_url": "https://api.slack.com/events/grid_migration_started",
    "scopes_required": [],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "app_event",
      "allows_workspace_tokens"
    ],
    "category": "grid",
    "label": "Grid Migration Started",
    "event_type": "grid_migration_started"
  },
  "group_archive": {
    "topic": "group.archive",
    "summary": "A private channel was archived",
    "doc_url": "https://api.slack.com/events/group_archive",
    "scopes_required": [
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "group",
    "label": "Group Archive",
    "event_type": "group_archive"
  },
  "group_close": {
    "topic": "group.close",
    "summary": "You closed a private channel",
    "doc_url": "https://api.slack.com/events/group_close",
    "scopes_required": [
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "group",
    "label": "Group Close",
    "event_type": "group_close"
  },
  "group_history_changed": {
    "topic": "group.history.changed",
    "summary": "Bulk updates were made to a private channel's history",
    "doc_url": "https://api.slack.com/events/group_history_changed",
    "scopes_required": [
      "groups:history"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "group",
    "label": "Group History Changed",
    "event_type": "group_history_changed"
  },
  "group_left": {
    "topic": "group.left",
    "summary": "You left a private channel",
    "doc_url": "https://api.slack.com/events/group_left",
    "scopes_required": [
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "group",
    "label": "Group Left",
    "event_type": "group_left"
  },
  "group_open": {
    "topic": "group.open",
    "summary": "You created a group DM",
    "doc_url": "https://api.slack.com/events/group_open",
    "scopes_required": [
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "group",
    "label": "Group Open",
    "event_type": "group_open"
  },
  "group_rename": {
    "topic": "group.rename",
    "summary": "A private channel was renamed",
    "doc_url": "https://api.slack.com/events/group_rename",
    "scopes_required": [
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "group",
    "label": "Group Rename",
    "event_type": "group_rename"
  },
  "group_unarchive": {
    "topic": "group.unarchive",
    "summary": "A private channel was unarchived",
    "doc_url": "https://api.slack.com/events/group_unarchive",
    "scopes_required": [
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "group",
    "label": "Group Unarchive",
    "event_type": "group_unarchive"
  },
  "im_close": {
    "topic": "im.close",
    "summary": "You closed a DM",
    "doc_url": "https://api.slack.com/events/im_close",
    "scopes_required": [
      "im:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "im",
    "label": "IM Close",
    "event_type": "im_close"
  },
  "im_created": {
    "topic": "im.created",
    "summary": "A DM was created",
    "doc_url": "https://api.slack.com/events/im_created",
    "scopes_required": [
      "im:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "im",
    "label": "IM Created",
    "event_type": "im_created"
  },
  "im_history_changed": {
    "topic": "im.history.changed",
    "summary": "Bulk updates were made to a DM's history",
    "doc_url": "https://api.slack.com/events/im_history_changed",
    "scopes_required": [
      "im:history"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "im",
    "label": "IM History Changed",
    "event_type": "im_history_changed"
  },
  "im_open": {
    "topic": "im.open",
    "summary": "You opened a DM",
    "doc_url": "https://api.slack.com/events/im_open",
    "scopes_required": [
      "im:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "im",
    "label": "IM Open",
    "event_type": "im_open"
  },
  "link_shared": {
    "topic": "link.shared",
    "summary": "A message was posted containing one or more links relevant to your application",
    "doc_url": "https://api.slack.com/events/link_shared",
    "scopes_required": [
      "links:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "link",
    "label": "Link Shared",
    "event_type": "link_shared"
  },
  "member_joined_channel": {
    "topic": "member.joined.channel",
    "summary": "A user joined a public or private channel",
    "doc_url": "https://api.slack.com/events/member_joined_channel",
    "scopes_required": [
      "channels:read",
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "member",
    "label": "Member Joined Channel",
    "event_type": "member_joined_channel"
  },
  "member_left_channel": {
    "topic": "member.left.channel",
    "summary": "A user left a public or private channel",
    "doc_url": "https://api.slack.com/events/member_left_channel",
    "scopes_required": [
      "channels:read",
      "groups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "member",
    "label": "Member Left Channel",
    "event_type": "member_left_channel"
  },
  "message": {
    "topic": "message",
    "summary": "A message was sent to a channel",
    "doc_url": "https://api.slack.com/events/message",
    "scopes_required": [
      "channels:history",
      "groups:history",
      "im:history",
      "mpim:history"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "message",
    "label": "Message",
    "event_type": "message"
  },
  "message_app_home": {
    "topic": "message.app.home",
    "summary": "A user sent a message to your Slack app",
    "doc_url": "https://api.slack.com/events/message.app_home",
    "scopes_required": [],
    "tokens_allowed": [
      "workspace"
    ],
    "tags": [
      "allows_workspace_tokens"
    ],
    "category": "message",
    "label": "Message App Home",
    "event_type": "message"
  },
  "message_channels": {
    "topic": "message.channels",
    "summary": "A message was posted to a channel",
    "doc_url": "https://api.slack.com/events/message.channels",
    "scopes_required": [
      "channels:history"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "message",
    "label": "Message Channels",
    "event_type": "message"
  },
  "message_groups": {
    "topic": "message.groups",
    "summary": "A message was posted to a private channel",
    "doc_url": "https://api.slack.com/events/message.groups",
    "scopes_required": [
      "groups:history"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "message",
    "label": "Message Groups",
    "event_type": "message"
  },
  "message_im": {
    "topic": "message.im",
    "summary": "A message was posted in a direct message channel",
    "doc_url": "https://api.slack.com/events/message.im",
    "scopes_required": [
      "im:history"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "message",
    "label": "Message IM",
    "event_type": "message"
  },
  "message_mpim": {
    "topic": "message.mpim",
    "summary": "A message was posted in a multiparty direct message channel",
    "doc_url": "https://api.slack.com/events/message.mpim",
    "scopes_required": [
      "mpim:history"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "message",
    "label": "Message MPIM",
    "event_type": "message"
  },
  "pin_added": {
    "topic": "pin.added",
    "summary": "A pin was added to a channel",
    "doc_url": "https://api.slack.com/events/pin_added",
    "scopes_required": [
      "pins:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "pin",
    "label": "Pin Added",
    "event_type": "pin_added"
  },
  "pin_removed": {
    "topic": "pin.removed",
    "summary": "A pin was removed from a channel",
    "doc_url": "https://api.slack.com/events/pin_removed",
    "scopes_required": [
      "pins:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "pin",
    "label": "Pin Removed",
    "event_type": "pin_removed"
  },
  "reaction_added": {
    "topic": "reaction.added",
    "summary": "A member has added an emoji reaction to an item",
    "doc_url": "https://api.slack.com/events/reaction_added",
    "scopes_required": [
      "reactions:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "reaction",
    "label": "Reaction Added",
    "event_type": "reaction_added"
  },
  "reaction_removed": {
    "topic": "reaction.removed",
    "summary": "A member removed an emoji reaction",
    "doc_url": "https://api.slack.com/events/reaction_removed",
    "scopes_required": [
      "reactions:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "reaction",
    "label": "Reaction Removed",
    "event_type": "reaction_removed"
  },
  "resources_added": {
    "topic": "resources.added",
    "summary": "Access to a set of resources was granted for your app",
    "doc_url": "https://api.slack.com/events/resources_added",
    "scopes_required": [],
    "tokens_allowed": [
      "workspace"
    ],
    "tags": [
      "allows_workspace_tokens"
    ],
    "category": "resources",
    "label": "Resources Added",
    "event_type": "resources_added"
  },
  "resources_removed": {
    "topic": "resources.removed",
    "summary": "Access to a set of resources was removed for your app",
    "doc_url": "https://api.slack.com/events/resources_removed",
    "scopes_required": [],
    "tokens_allowed": [
      "workspace"
    ],
    "tags": [
      "allows_workspace_tokens"
    ],
    "category": "resources",
    "label": "Resources Removed",
    "event_type": "resources_removed"
  },
  "scope_denied": {
    "topic": "scope.denied",
    "summary": "OAuth scopes were denied to your app",
    "doc_url": "https://api.slack.com/events/scope_denied",
    "scopes_required": [],
    "tokens_allowed": [
      "workspace"
    ],
    "tags": [
      "allows_workspace_tokens"
    ],
    "category": "scope",
    "label": "Scope Denied",
    "event_type": "scope_denied"
  },
  "scope_granted": {
    "topic": "scope.granted",
    "summary": "OAuth scopes were granted to your app",
    "doc_url": "https://api.slack.com/events/scope_granted",
    "scopes_required": [],
    "tokens_allowed": [
      "workspace"
    ],
    "tags": [
      "allows_workspace_tokens"
    ],
    "category": "scope",
    "label": "Scope Granted",
    "event_type": "scope_granted"
  },
  "star_added": {
    "topic": "star.added",
    "summary": "A member has starred an item",
    "doc_url": "https://api.slack.com/events/star_added",
    "scopes_required": [
      "stars:read"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "star",
    "label": "Star Added",
    "event_type": "star_added"
  },
  "star_removed": {
    "topic": "star.removed",
    "summary": "A member removed a star",
    "doc_url": "https://api.slack.com/events/star_removed",
    "scopes_required": [
      "stars:read"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "star",
    "label": "Star Removed",
    "event_type": "star_removed"
  },
  "subteam_created": {
    "topic": "subteam.created",
    "summary": "A User Group has been added to the workspace",
    "doc_url": "https://api.slack.com/events/subteam_created",
    "scopes_required": [
      "usergroups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "subteam",
    "label": "Subteam Created",
    "event_type": "subteam_created"
  },
  "subteam_members_changed": {
    "topic": "subteam.members.changed",
    "summary": "The membership of an existing User Group has changed",
    "doc_url": "https://api.slack.com/events/subteam_members_changed",
    "scopes_required": [
      "usergroups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "subteam",
    "label": "Subteam Members Changed",
    "event_type": "subteam_members_changed"
  },
  "subteam_self_added": {
    "topic": "subteam.self.added",
    "summary": "You have been added to a User Group",
    "doc_url": "https://api.slack.com/events/subteam_self_added",
    "scopes_required": [
      "usergroups:read"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "subteam",
    "label": "Subteam Self Added",
    "event_type": "subteam_self_added"
  },
  "subteam_self_removed": {
    "topic": "subteam.self.removed",
    "summary": "You have been removed from a User Group",
    "doc_url": "https://api.slack.com/events/subteam_self_removed",
    "scopes_required": [
      "usergroups:read"
    ],
    "tokens_allowed": [
      "user"
    ],
    "tags": [
      "allows_user_tokens"
    ],
    "category": "subteam",
    "label": "Subteam Self Removed",
    "event_type": "subteam_self_removed"
  },
  "subteam_updated": {
    "topic": "subteam.updated",
    "summary": "An existing User Group has been updated or its members changed",
    "doc_url": "https://api.slack.com/events/subteam_updated",
    "scopes_required": [
      "usergroups:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "subteam",
    "label": "Subteam Updated",
    "event_type": "subteam_updated"
  },
  "team_domain_change": {
    "topic": "team.domain.change",
    "summary": "The workspace domain has changed",
    "doc_url": "https://api.slack.com/events/team_domain_change",
    "scopes_required": [
      "team:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "team",
    "label": "Team Domain Change",
    "event_type": "team_domain_change"
  },
  "team_join": {
    "topic": "team.join",
    "summary": "A new member has joined",
    "doc_url": "https://api.slack.com/events/team_join",
    "scopes_required": [
      "users:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "team",
    "label": "Team Join",
    "event_type": "team_join"
  },
  "team_rename": {
    "topic": "team.rename",
    "summary": "The workspace name has changed",
    "doc_url": "https://api.slack.com/events/team_rename",
    "scopes_required": [
      "team:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "team",
    "label": "Team Rename",
    "event_type": "team_rename"
  },
  "tokens_revoked": {
    "topic": "tokens.revoked",
    "summary": "API tokens for your app were revoked.",
    "doc_url": "https://api.slack.com/events/tokens_revoked",
    "scopes_required": [],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "app_event",
      "allows_workspace_tokens"
    ],
    "category": "tokens",
    "label": "Tokens Revoked",
    "event_type": "tokens_revoked"
  },
  "user_change": {
    "topic": "user.change",
    "summary": "A member's data has changed",
    "doc_url": "https://api.slack.com/events/user_change",
    "scopes_required": [
      "users:read"
    ],
    "tokens_allowed": [
      "user",
      "workspace"
    ],
    "tags": [
      "allows_user_tokens",
      "allows_workspace_tokens"
    ],
    "category": "user",
    "label": "User Change",
    "event_type": "user_change"
  }
}
