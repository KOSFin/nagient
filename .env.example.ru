# Конфигурация Nagient для Docker Compose.
# Скопируйте файл в .env и измените только нужные значения:
#   cp .env.example.ru .env

NAGIENT_IMAGE=docker.io/parampo/nagient:latest
NAGIENT_CONTAINER_NAME=nagient
NAGIENT_HEARTBEAT_INTERVAL=30
NAGIENT_SAFE_MODE=true
NAGIENT_WORKSPACE_MODE=bounded
NAGIENT_AGENT__MAX_TURNS=12
NAGIENT_AGENT_REQUIRE_PROVIDER=false

# Провайдер: включите один блок и укажите секрет в том же .env.
# Секрет хранится под именем OPENAI_API_KEY, а не в конфигурации провайдера.
# NAGIENT_AGENT_DEFAULT_PROVIDER=openai
# NAGIENT_AGENT_REQUIRE_PROVIDER=true
# NAGIENT_PROVIDER__OPENAI__PLUGIN=builtin.openai
# NAGIENT_PROVIDER__OPENAI__ENABLED=true
# NAGIENT_PROVIDER__OPENAI__AUTH=api_key
# NAGIENT_PROVIDER__OPENAI__API_KEY_SECRET=OPENAI_API_KEY
# NAGIENT_PROVIDER__OPENAI__MODEL=gpt-4.1-mini
# OPENAI_API_KEY=вставьте-ключ-сюда

# Другие встроенные провайдеры используют тот же шаблон:
# NAGIENT_PROVIDER__DEEPSEEK__PLUGIN=builtin.deepseek
# NAGIENT_PROVIDER__DEEPSEEK__ENABLED=true
# NAGIENT_PROVIDER__DEEPSEEK__AUTH=api_key
# NAGIENT_PROVIDER__DEEPSEEK__API_KEY_SECRET=DEEPSEEK_API_KEY
# NAGIENT_PROVIDER__DEEPSEEK__MODEL=deepseek-chat
# DEEPSEEK_API_KEY=вставьте-ключ-сюда
# Для OpenAI-совместимого API задайте также NAGIENT_PROVIDER__ID__BASE_URL.

# Telegram — внешний плагин. Сначала добавьте его закреплённый репозиторий в
# NAGIENT_PLUGIN_SPECS, затем включите профиль.
# NAGIENT_TRANSPORT__CONSOLE__ENABLED=false
# NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
# NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
# NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
# NAGIENT_TRANSPORT__TELEGRAM__DEFAULT_CHAT_ID=123456789
# TELEGRAM_BOT_TOKEN=вставьте-токен-сюда
# По умолчанию плагин игнорирует группы. Разрешайте только нужных пользователей.
# NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=private
# NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
# NAGIENT_TRANSPORT__TELEGRAM__GROUP_REPLY_MODE=off
# NAGIENT_TRANSPORT__TELEGRAM__GROUP_REPLY_MODE=mentions
# NAGIENT_TRANSPORT__TELEGRAM__BOT_USERNAME=my_nagient_bot
# Необязательный HTTP/HTTPS-прокси для всех запросов Telegram Bot API
# (polling и отправка ответов).
# NAGIENT_TRANSPORT__TELEGRAM__PROXY_URL=http://proxy.example:8080
# Необязательная авторизация прокси. Пароль храните как секрет.
# NAGIENT_TRANSPORT__TELEGRAM__PROXY_USERNAME=proxy-user
# NAGIENT_TRANSPORT__TELEGRAM__PROXY_PASSWORD_SECRET=TELEGRAM_PROXY_PASSWORD
# TELEGRAM_PROXY_PASSWORD=замените-значение

# Необязательная локальная панель оператора. Она хранит профили в ./data/config.toml.
# ENV остаются bootstrap-lock. Для публикации порта подключите docker-compose.control-panel.yml.
# NAGIENT_CONTROL_PANEL_ENABLED=true
# NAGIENT_CONTROL_PANEL_PASSWORD=задайте-длинный-пароль
# NAGIENT_CONTROL_PANEL_BIND_ADDRESS=127.0.0.1
# NAGIENT_CONTROL_PANEL_PORT=8787

# Вебхук по умолчанию доступен только на localhost.
# NAGIENT_TRANSPORT__WEBHOOK__PLUGIN=builtin.webhook
# NAGIENT_TRANSPORT__WEBHOOK__ENABLED=true
# NAGIENT_TRANSPORT__WEBHOOK__LISTEN_HOST=0.0.0.0
# NAGIENT_TRANSPORT__WEBHOOK__LISTEN_PORT=8080
# NAGIENT_TRANSPORT__WEBHOOK__PATH=/events
# NAGIENT_TRANSPORT__WEBHOOK__SHARED_SECRET_NAME=NAGIENT_WEBHOOK_SHARED_SECRET
# NAGIENT_WEBHOOK_SHARED_SECRET=замените-значение
# NAGIENT_WEBHOOK_BIND_ADDRESS=127.0.0.1
# NAGIENT_WEBHOOK_PORT=8080

# Установка внешних плагинов при первом запуске контейнера.
# Один репозиторий на элемент, разделитель — запятая. Фиксируйте tag/commit.
# NAGIENT_PLUGIN_SPECS=https://github.com/KOSFin/nagient-transport-telegram.git#v0.2.1

# GitHub API — внешний плагин. Добавьте его репозиторий в NAGIENT_PLUGIN_SPECS.
# NAGIENT_TOOL__GITHUB_API__PLUGIN=nagient.github_api
# NAGIENT_TOOL__GITHUB_API__ENABLED=true
# NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET=GITHUB_TOKEN
# GITHUB_TOKEN=вставьте-токен-сюда
