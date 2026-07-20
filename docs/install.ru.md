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
nagient update
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" update
```

## 4. Удаление

Linux/macOS:

```bash
nagient remove
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

Полная очистка данных:

Linux/macOS:

```bash
NAGIENT_PURGE=true nagient remove
```

Windows:

```powershell
$env:NAGIENT_PURGE = "true"
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

## 5. Требования

Для обычного установщика нужны Docker Engine 24+, Docker Compose v2 и
`bash`/`curl` на Linux/macOS либо PowerShell 7+ на Windows.

Для установки без Docker нужны Python 3.11+ и `bash` на Linux/macOS либо
PowerShell 7+ на Windows. Docker в этом режиме не требуется.

## 6. Runtime без Docker

Обычный release-установщик использует Docker Compose. Если на персональном
компьютере Docker недоступен, установите runtime напрямую из checkout:

```bash
bash scripts/install-local.sh --home "$HOME/.nagient" --source .
export PATH="$HOME/.nagient/bin:$PATH"
nagient setup
nagient status
```

Скрипт создаёт virtualenv Python 3.11+, хранит состояние в `~/.nagient` и
запускает `nagient serve` как фоновый процесс. Docker не нужен; при запуске из
source checkout build-зависимости не скачиваются. Управление: `nagient
start|stop|restart|logs`. В Windows используйте `scripts/install-local.ps1` из
PowerShell.
