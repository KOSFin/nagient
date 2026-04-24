# Архитектурные заметки

Nagient разделён на узкую control-surface часть и централизованную release/update модель.

## Слои

- `nagient.app` связывает settings и сервисы.
- `nagient.application.services` содержит use-case логику, например health-check и поиск обновлений.
- `nagient.domain` владеет release-сущностями и сравнением семантических версий.
- `nagient.infrastructure` отвечает за manifests, registry loading, runtime heartbeat и файловый transport.
- `nagient.migrations` строит упорядоченный план upgrade-шагов из release metadata.

## Контракт update center

У update center два основных JSON-документа:

1. `channels/<channel>.json` указывает на актуальный release manifest канала.
2. `manifests/<version>.json` описывает Docker image, установщики, deployment assets, миграции и release notices.

Именно этот контракт должны одинаково читать shell-установщики, PowerShell-установщики, CLI и будущие каналы уведомлений.

## Модель поставки

Тег `vX.Y.Z` должен порождать:

1. Python-дистрибутив в `dist/`.
2. Docker image `docker.io/<namespace>/<image>:X.Y.Z`.
3. Versioned installer assets по адресу `<update-base-url>/X.Y.Z/`.
4. Release manifest по адресу `<update-base-url>/manifests/X.Y.Z.json`.
5. Указатель канала по адресу `<update-base-url>/channels/stable.json`.

