# Telegram Transport

Use `telegram.sendMessage` for normal replies and direct outbound messages.
Use `telegram.sendNotification` for low-priority notices.
Use `telegram.sendTyping` or `telegram.sendChatAction` before longer responses when a chat target is known.
Use `telegram.editMessage`, `telegram.deleteMessage`, and `telegram.setReaction` only when the inbound event or caller provides a valid `chat_id` and `message_id`.
Use `telegram.answerCallback` or `telegram.showPopup` for callback query acknowledgements.
For formatted messages, pass `parse_mode` as `MarkdownV2`, `HTML`, or `Markdown`; the transport also supports `default_parse_mode` in config.
Telegram service commands such as `/start`, `/help`, `/settings`, and `/stop` are normalized as command events so they do not trigger a normal agent turn.

Inbound Telegram updates must be normalized before they reach the agent runtime. Normalized message events should include:

```json
{
  "kind": "telegram",
  "event_type": "message",
  "session_id": "telegram:<chat_id>",
  "text": "User message text",
  "reply_target": {
    "chat_id": "<chat_id>"
  },
  "payload": {}
}
```

When sending from another transport, call the transport router with `transport_id = "telegram"` and either provide `payload.chat_id` or configure `default_chat_id`.
