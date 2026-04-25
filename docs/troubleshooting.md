# Troubleshooting

## Docker is required

Симптом: installer падает с ошибкой про Docker.

Проверьте:

1. Docker установлен.
2. Docker daemon запущен.
3. `docker` доступен в PATH.

## NAGIENT_UPDATE_BASE_URL is not configured

Симптом: ошибка в install/update script.

Причина: запуск шаблонного скрипта из репозитория вместо release-asset.

Используйте:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

или

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

## preflight/reconcile error

Проверьте:

1. Включен ли provider в `config.toml`.
2. Есть ли секреты в `secrets.env`.
3. Доступны ли пользовательские plugins.

Команды:

```bash
~/.nagient/bin/nagientctl preflight
~/.nagient/bin/nagientctl reconcile
~/.nagient/bin/nagientctl status
```

## Не нравится длинный путь к nagientctl

Сделайте alias.

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
