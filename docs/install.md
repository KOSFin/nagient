# Install

Language: English | [Русский](install.ru.md)

Update center URL: `https://ngnt-in.ruka.me`
Docker image: `docker.io/parampo/nagient`

## 1. Install latest

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

What the installer does:

1. Reads `channels/stable.json`.
2. Resolves the latest version.
3. Downloads versioned `install.sh` or `install.ps1`.
4. Creates runtime in `~/.nagient`.
5. Starts the container via Docker Compose.

## 2. Install a specific version

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/0.1.0/install.sh | bash
```

Windows:

```powershell
Invoke-Expression ((Invoke-WebRequest -UseBasicParsing -Uri "https://ngnt-in.ruka.me/0.1.0/install.ps1").Content)
```

## 3. Update

Linux/macOS:

```bash
~/.nagient/bin/nagient update
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" update
```

## 4. Remove

Linux/macOS:

```bash
~/.nagient/bin/nagient remove
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

Full data cleanup:

Linux/macOS:

```bash
NAGIENT_PURGE=true ~/.nagient/bin/nagient remove
```

Windows:

```powershell
$env:NAGIENT_PURGE = "true"
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

## 5. Requirements

- Docker Engine 24+
- Docker Compose v2
- Linux/macOS: `bash` + `curl`/`wget`
- Windows: PowerShell 7+
