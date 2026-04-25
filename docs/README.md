# Nagient Docs

Коротко: теперь для установки и управления есть короткие команды без длинных compose-строк.

## Быстрый старт

Linux/macOS:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
~/.nagient/bin/nagientctl up
~/.nagient/bin/nagientctl status
```

Windows PowerShell:

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagientctl.ps1" up
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagientctl.ps1" status
```

## Навигация

- Установка и обновления: [install.md](install.md)
- Короткие и полные команды: [commands.md](commands.md)
- Настройка config и secrets: [configuration.md](configuration.md)
- Справочник переменных окружения: [env.md](env.md)
- Частые проблемы и решения: [troubleshooting.md](troubleshooting.md)
- Архитектура: [architecture.ru.md](architecture.ru.md)

## Что изменилось

- Добавлен bootstrap installer в корень update center: `install.sh` и `install.ps1`.
- Добавлен `nagientctl` (bash) и `nagientctl.ps1` (PowerShell) для короткого управления.
- Документация разделена на тематические страницы.

Сделано с любовью и уважением к времени пользователя.
