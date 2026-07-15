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

## 2. Configure (optional)

The defaults work out of the box. To pin a specific image version or rename the
container, copy the example environment file and edit it:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `NAGIENT_IMAGE` | `docker.io/parampo/nagient:latest` | Image and tag to run. Pin to a version like `:0.8.8` in production. |
| `NAGIENT_CONTAINER_NAME` | `nagient` | Container name. |
| `NAGIENT_HEARTBEAT_INTERVAL` | `30` | Heartbeat write interval, seconds. |
| `NAGIENT_SAFE_MODE` | `true` | Keep workspace path guards on. |

## 3. First start

```bash
docker compose up -d
```

On first start the container seeds `config.toml` and `secrets.env` into `./data`
on the host. No host files need to exist beforehand.

## 4. Add secrets

Edit `./data/secrets.env` and add the keys for the providers and transports you
plan to use:

```dotenv
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
```

## 5. Enable a provider and a transport

Edit `./data/config.toml`:

```toml
[agent]
default_provider = "openai"

[providers.openai]
enabled = true

[transports.telegram]
enabled = true
default_chat_id = "123456789"
```

Then apply the changes:

```bash
docker compose restart
```

## 6. Verify

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

## Notes

- Secrets are read from `./data/secrets.env`, not from shell environment
  variables. Keep that file out of version control.
- To expose the webhook transport, publish its port by adding a `ports:` entry
  to the `nagient` service and enabling `[transports.webhook]` in `config.toml`.
