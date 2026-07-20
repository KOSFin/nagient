# Plugins

Language: English | [Русский](plugins.ru.md)

Nagient separates the runtime from extensions. A plugin is a repository with a
manifest (`plugin.toml`, `provider.toml`, or `tool.toml`), its own instructions,
and optional isolated dependencies. Installed plugins live under `~/.nagient`;
they are never copied into the core package.

## Discover and install

Start with the reviewed catalog:

```bash
nagient plugin catalog list
nagient plugin catalog list --family transport
nagient plugin list
```

`bundled` entries are already part of Nagient. External entries can be installed
without hunting through GitHub:

```bash
nagient plugin catalog install <plugin-id>
nagient preflight
nagient status
```

Official separately versioned repositories:

| Plugin | Install |
| --- | --- |
| `nagient.telegram` | `nagient plugin catalog install nagient.telegram` |
| `nagient.github_api` | `nagient plugin catalog install nagient.github_api` |

Use `--format json` in scripts. The catalog distinguishes `verified` entries
from arbitrary repositories. A repository installed directly is still supported,
but it is not treated as reviewed:

```bash
nagient plugin install transport:https://github.com/ORG/REPO.git#v1.0.0
```

## Telegram

Telegram is bundled and enabled by configuration. The token is always a secret
reference, never a value committed to a config file:

```env
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN=123456:replace-me
```

Group and sender restrictions are opt-in. If a list is non-empty, events outside
the list are acknowledged and ignored before they reach the agent:

```env
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890,123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=private,supergroup
```

The transport also exposes `telegram.streamMessage`. A runtime integration can
send cumulative provider snapshots in one message and progressively edit it, while
respecting Telegram's rate limits by batching updates.

## Configuration owned by a plugin

Every plugin declares its fields in its manifest. The environment name follows
one rule, so adding a plugin does not require a Compose change:

```text
NAGIENT_<FAMILY>__<PLUGIN_ID>__<FIELD>=value
```

For example, `allowed_chat_ids` becomes
`NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS`. Secret fields contain a secret
name; the value belongs in the environment or `NAGIENT_SECRETS_JSON`.

## Trust and updates

Review `plugin.toml`, the source URL, and the pinned `#ref` before installing an
unverified plugin. Run `nagient preflight` after every install and keep tools in
bounded workspace mode unless a workflow explicitly needs broader access.
