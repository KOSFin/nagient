# User: Plugins

Language: English | [Русский](plugins.ru.md)

## 1. Find a plugin

```bash
nagient plugin catalog list
nagient plugin catalog list --family transport
```

The short text output is meant for a terminal screen. Add `--format json` for
automation. Use `nagient plugin list` to see only external repositories already
installed in the runtime.

## 2. Install on a personal computer

```bash
nagient plugin catalog install <plugin-id>
nagient preflight
nagient reconcile
```

Restart the runtime after a configuration change:

```bash
nagient restart
```

## 3. Install with Docker Compose

Run commands inside the persistent container. The plugin is stored in `./data`
and survives a restart:

```bash
docker compose exec nagient nagient plugin catalog list
docker compose exec nagient nagient plugin catalog install <plugin-id>
docker compose exec nagient nagient preflight
docker compose restart nagient
```

For unattended deployments, put a pinned Git source in `NAGIENT_PLUGIN_SPECS` in
`.env` and run `docker compose up -d`. Use a tag or commit, not a floating branch.

Official plugin examples:

```bash
docker compose exec nagient nagient plugin catalog install nagient.telegram
docker compose exec nagient nagient plugin catalog install nagient.github_api
```

## 4. Configure a plugin

Read the plugin's fields from the catalog JSON or its manifest. The universal
environment shape is:

```text
NAGIENT_<FAMILY>__<PLUGIN_ID>__<FIELD>=value
```

Secret fields contain a secret name. Never put a token directly in a public
Compose file.

## 5. Telegram safety

Telegram is bundled. Restrict group bots before enabling them:

```env
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=supergroup
```
