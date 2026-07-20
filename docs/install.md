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
nagient update
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" update
```

## 4. Remove

Linux/macOS:

```bash
nagient remove
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

Full data cleanup:

Linux/macOS:

```bash
NAGIENT_PURGE=true nagient remove
```

Windows:

```powershell
$env:NAGIENT_PURGE = "true"
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

## 5. Requirements

For the standard installer: Docker Engine 24+ and Docker Compose v2, plus
`bash`/`curl` on Linux/macOS or PowerShell 7+ on Windows.

For the Docker-free installer: Python 3.11+ and `bash` on Linux/macOS, or
PowerShell 7+ on Windows. Docker is not required in this mode.

## 6. Docker-free local runtime

The standard release installer is Docker Compose based. For a personal computer
where Docker is unavailable, install directly from a checkout:

```bash
bash scripts/install-local.sh --home "$HOME/.nagient" --source .
export PATH="$HOME/.nagient/bin:$PATH"
nagient setup
nagient status
```

This creates a Python 3.11+ virtual environment, keeps runtime state under
`~/.nagient`, and runs `nagient serve` as a background process. It does not
install Docker or download build dependencies when run from a source checkout.
Use `nagient start|stop|restart|logs` to manage the local process. Windows users
can run `scripts/install-local.ps1` from PowerShell.
