# Plugins For Operators

English · [Русская версия](plugins.ru.md) · [Plugin Hub reference](../plugins.md)

## Personal Computer

Open the interactive installer:

```bash
nagient plugin install
```

Or install directly by verified ID or Git URL:

```bash
nagient plugin install nagient.telegram
nagient plugin install https://github.com/owner/nagient-plugin.git --ref v1.0.0
nagient preflight
nagient restart
```

## Docker Compose

```bash
docker compose exec nagient nagient plugin install
docker compose exec nagient nagient plugin install nagient.telegram
docker compose exec nagient nagient preflight
docker compose restart nagient
```

The plugin is stored in the persistent runtime data, so a normal restart does not remove it. For unattended deployment, use pinned repositories in `NAGIENT_PLUGIN_SPECS`; see [server deployment](../deploy.md#3-install-external-plugins).

## Configuration

Installation and activation are separate steps. Set the plugin ID on a profile and enable it:

```env
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN=123456:replace-me
```

Restrict Telegram before adding a bot to groups:

```env
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=supergroup
```

## Inspect Or Remove

```bash
nagient plugin list
nagient plugin remove nagient.telegram
nagient preflight
```

See the [complete Plugin Hub guide](../plugins.md) for catalog status, updates, flags, trust, and Git source rules.
