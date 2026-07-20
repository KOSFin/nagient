# Nagient Documentation

Language: English | [Русский](README.ru.md)

## Quick Start

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
nagient setup
nagient chat
nagient up
nagient status
```

Windows PowerShell:

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" up
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" status
```

## Navigation

Choose the path that matches your role:

- **User:** [User Guide](user/README.md)
- **Developer:** [Developer Guide](developer/README.md)

- Installation and updates: [install.md](install.md)
- Self-hosted Docker Compose deployment: [deploy.md](deploy.md)
- Runtime and CLI commands: [commands.md](commands.md)
- Configuration and secrets: [configuration.md](configuration.md)
- Plugin contracts: [plugin-contracts.md](plugin-contracts.md)
- Official plugin catalog and Telegram: [plugins.md](plugins.md)
- Environment variables: [env.md](env.md)
- Troubleshooting: [troubleshooting.md](troubleshooting.md)
- Architecture: [architecture.md](architecture.md)
