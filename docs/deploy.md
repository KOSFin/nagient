# Deploy with Docker Compose

Language: English | [Русский](deploy.ru.md)

This guide covers deploying Nagient on your own server with Docker Compose,
without the hosted installer script. Use this when you want full control over
the runtime, or when the machine cannot reach the hosted update center.

## Requirements

- Docker Engine 24+
- Docker Compose v2 (`docker compose`, not the legacy `docker-compose`)
- A provider API key (OpenAI, Anthropic, Gemini, DeepSeek, or a local Ollama)

## 1. Get the compose file

Clone the repository (or copy `docker-compose.yml` and `.env.example` onto the
server):

```bash
git clone https://github.com/KOSFin/nagient.git
cd nagient
```

## 2. Configure through environment variables

Copy the example and set everything the runtime needs in one file:

```bash
cp .env.example .env
chmod 600 .env
```

For example, an OpenAI provider with Telegram needs only these uncommented
values in `.env`:

```dotenv
NAGIENT_AGENT_DEFAULT_PROVIDER=openai
NAGIENT_AGENT_REQUIRE_PROVIDER=true
NAGIENT_PROVIDER__OPENAI__PLUGIN=builtin.openai
NAGIENT_PROVIDER__OPENAI__ENABLED=true
NAGIENT_PROVIDER__OPENAI__AUTH=api_key
NAGIENT_PROVIDER__OPENAI__API_KEY_SECRET=OPENAI_API_KEY
NAGIENT_PROVIDER__OPENAI__MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...

NAGIENT_TRANSPORT__CONSOLE__ENABLED=false
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
NAGIENT_TRANSPORT__TELEGRAM__DEFAULT_CHAT_ID=123456789
TELEGRAM_BOT_TOKEN=123456:ABC...

NAGIENT_PLUGIN_SPECS=https://github.com/KOSFin/nagient-transport-telegram.git#v0.1.0
```

The compose service loads the entire `.env` into the container. You do not need
to run `nagient setup`, edit TOML, or edit a generated secrets file.

## 3. Install External Plugins

For unattended deployment, list pinned Git repositories in `.env`:

```dotenv
NAGIENT_PLUGIN_SPECS=https://github.com/KOSFin/nagient-transport-telegram.git#v0.1.0,https://github.com/KOSFin/nagient-tool-github-api.git#v0.1.0
```

On first boot, the entrypoint clones each repository, validates its manifest,
and stores it under persistent `./data`. For an existing container, open Plugin
Hub or install a verified ID directly:

```bash
docker compose exec nagient nagient plugin install
docker compose exec nagient nagient plugin install nagient.telegram
```

## 4. First start

```bash
docker compose up -d
```

On first start the container also seeds compatibility files under `./data`.
They are useful for persistence and CLI workflows, but environment values take
precedence and no manual interaction with those files is required.

## 5. Verify

```bash
docker compose exec nagient nagient status
docker compose exec nagient nagient doctor --format json
docker compose logs -f nagient
```

`nagient doctor` also backs the container healthcheck, so `docker compose ps`
shows `healthy` once the runtime is ready.

## Data layout

Everything lives under two host directories, both easy to back up:

- `./data` — config, secrets, state, logs, credentials, and installed plugins.
- `./workspace` — the bounded workspace the agent reads and writes.

## Configuration model

Every current configuration field is available without CLI interaction:

- common settings use variables such as `NAGIENT_SAFE_MODE`,
  `NAGIENT_WORKSPACE_MODE`, and `NAGIENT_AGENT__MAX_TURNS`;
- provider, transport, and tool fields use
  `NAGIENT_PROVIDER__<ID>__<FIELD>`, `NAGIENT_TRANSPORT__<ID>__<FIELD>`, and
  `NAGIENT_TOOL__<ID>__<FIELD>`;
- referenced secrets such as `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, and custom
  plugin secret names are read directly from the container environment;
- `NAGIENT_CONFIG_JSON` deep-merges a complete TOML-shaped JSON object for
  nested or future fields;
- `NAGIENT_SECRETS_JSON` and `NAGIENT_TOOL_SECRETS_JSON` accept arbitrary
  secret-name/value objects.

Precedence is: granular environment variables, JSON environment configuration,
persisted files, built-in defaults. See [env.md](env.md) for the full reference.

To use a differently named environment file:

```bash
NAGIENT_ENV_FILE=/srv/nagient/production.env \
  docker compose --env-file /srv/nagient/production.env up -d
```

## Upgrade

Pin a new tag in `.env` (or keep `:latest`) and pull:

```bash
docker compose pull
docker compose up -d
```

## Remove

```bash
docker compose down
```

To also delete runtime data, remove the host directories:

```bash
rm -rf ./data ./workspace
```

## Webhook exposure

Compose publishes the configured webhook container port on `127.0.0.1:8080` by
default. Set `NAGIENT_WEBHOOK_BIND_ADDRESS=0.0.0.0` and
`NAGIENT_WEBHOOK_PORT=<host-port>` only when external access is required and the
endpoint is protected by a firewall or reverse proxy.
