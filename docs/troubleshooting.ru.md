# Диагностика проблем

Язык: [English](troubleshooting.md) | Русский

## Требуется Docker

Симптом: установщик падает с ошибкой про Docker.

Проверьте:

1. Docker установлен.
2. Docker daemon запущен.
3. `docker` доступен в `PATH`.

## NAGIENT_UPDATE_BASE_URL is not configured

Симптом: ошибка в install/update скрипте.

Причина: запуск шаблонного скрипта из репозитория вместо опубликованного release-asset.

Используйте:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

или

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

## Ошибка preflight/reconcile

Проверьте:

1. Provider включен в `config.toml`.
2. Секреты добавлены в `secrets.env`.
3. Пользовательские plugins доступны runtime.

Команды:

```bash
~/.nagient/bin/nagientctl preflight
~/.nagient/bin/nagientctl reconcile
~/.nagient/bin/nagientctl status
```

## Слишком длинный путь до `nagientctl`

Создайте alias.

Linux/macOS:

```bash
alias ng='~/.nagient/bin/nagientctl'
ng status
```

PowerShell:

```powershell
Set-Alias ng "$HOME/.nagient/bin/nagientctl.ps1"
ng status
```
