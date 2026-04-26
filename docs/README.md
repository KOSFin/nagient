# Nagient Documentation

Language: English | [Русский](README.ru.md)

## Quick Start

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
~/.nagient/bin/nagient setup
~/.nagient/bin/nagient chat
~/.nagient/bin/nagient up
~/.nagient/bin/nagient status
```

Windows PowerShell:

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" up
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" status
```

## Navigation

- Installation and updates: [install.md](install.md)
- Runtime and CLI commands: [commands.md](commands.md)
- Configuration and secrets: [configuration.md](configuration.md)
- Environment variables: [env.md](env.md)
- Troubleshooting: [troubleshooting.md](troubleshooting.md)
- Architecture: [architecture.md](architecture.md)
