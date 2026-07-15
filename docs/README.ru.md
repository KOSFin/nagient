# Документация Nagient

Язык: [English](README.md) | Русский

## Быстрый старт

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

## Навигация

- Установка и обновления: [install.ru.md](install.ru.md)
- Развёртывание через Docker Compose: [deploy.ru.md](deploy.ru.md)
- Команды runtime и CLI: [commands.ru.md](commands.ru.md)
- Конфигурация и секреты: [configuration.ru.md](configuration.ru.md)
- Контракты плагинов: [plugin-contracts.ru.md](plugin-contracts.ru.md)
- Переменные окружения: [env.ru.md](env.ru.md)
- Диагностика проблем: [troubleshooting.ru.md](troubleshooting.ru.md)
- Архитектура: [architecture.ru.md](architecture.ru.md)
