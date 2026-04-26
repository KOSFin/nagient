# Диагностика проблем

Язык: [English](troubleshooting.md) | Русский

## Требуется Docker

Симптом: установщик падает с ошибкой про Docker.

Проверьте:

1. Docker установлен.
2. Docker daemon запущен.
3. `docker` доступен в `PATH`.
4. `docker compose version` выполняется без ошибки.
5. `docker info` выполняется без ошибки.

Типичный симптом на macOS:

```text
failed to connect to the docker API at unix:///Users/<user>/.docker/run/docker.sock
```

Обычно это значит, что Docker Desktop еще не запущен.

## Несовпадение архитектуры образа на Apple Silicon

Симптом:

```text
no matching manifest for linux/arm64/v8 in the manifest list entries
```

Причина: опубликованный Docker tag пока не содержит `arm64`-образ.

Временный обходной путь на Apple Silicon:

```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

Так будет запущен `amd64`-образ через эмуляцию, пока не опубликован multi-arch release.

## NAGIENT_UPDATE_BASE_URL is not configured

Симптом: ошибка в install/update скрипте.

Причина: update center отдает не сгенерированный bootstrap-скрипт, а шаблон или устаревший snapshot ветки.

Проверьте:

1. В `Settings -> Pages` выбран источник `GitHub Actions` или ветка `gh-pages`.
2. Repository variable `UPDATE_BASE_URL` указывает на публичный URL update center.
3. После изменения `UPDATE_BASE_URL` или `CUSTOM_DOMAIN` workflow `Update Center` был перезапущен.
4. В `https://ваш-домен/install.sh` нет строки `__NAGIENT_UPDATE_BASE_URL__`.

Используйте:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

или

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

Примечания:

- `NAGIENT_UPDATE_BASE_URL` не является GitHub repository variable.
- Установщик встраивает его автоматически из `UPDATE_BASE_URL`.

## Ошибка preflight/reconcile

Проверьте:

1. Provider включен в `config.toml`.
2. Секреты добавлены в `secrets.env`.
3. Пользовательские plugins доступны runtime.

Команды:

```bash
~/.nagient/bin/nagient preflight
~/.nagient/bin/nagient reconcile
~/.nagient/bin/nagient status
```

## Слишком длинный путь до `nagient`

Создайте alias.

Linux/macOS:

```bash
alias ng='~/.nagient/bin/nagient'
ng status
```

PowerShell:

```powershell
Set-Alias ng "$HOME/.nagient/bin/nagient.ps1"
ng status
```
