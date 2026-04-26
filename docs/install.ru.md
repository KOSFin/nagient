# Установка

Язык: [English](install.md) | Русский

URL update center: `https://ngnt-in.ruka.me`
Docker image: `docker.io/parampo/nagient`

## 1. Установка latest

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

Что делает установщик:

1. Читает `channels/stable.json`.
2. Определяет актуальную версию.
3. Скачивает версионные `install.sh` или `install.ps1`.
4. Создаёт runtime в `~/.nagient`.
5. Поднимает контейнер через Docker Compose.

## 2. Установка конкретной версии

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/0.1.0/install.sh | bash
```

Windows:

```powershell
Invoke-Expression ((Invoke-WebRequest -UseBasicParsing -Uri "https://ngnt-in.ruka.me/0.1.0/install.ps1").Content)
```

## 3. Обновление

Linux/macOS:

```bash
~/.nagient/bin/nagient update
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" update
```

## 4. Удаление

Linux/macOS:

```bash
~/.nagient/bin/nagient remove
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

Полная очистка данных:

Linux/macOS:

```bash
NAGIENT_PURGE=true ~/.nagient/bin/nagient remove
```

Windows:

```powershell
$env:NAGIENT_PURGE = "true"
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

## 5. Требования

- Docker Engine 24+
- Docker Compose v2
- Linux/macOS: `bash` + `curl`/`wget`
- Windows: PowerShell 7+
