FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NAGIENT_HOME=/var/lib/nagient \
    NAGIENT_CONFIG=/var/lib/nagient/config/config.toml \
    NAGIENT_SECRETS_FILE=/var/lib/nagient/secrets.env \
    NAGIENT_PLUGINS_DIR=/var/lib/nagient/plugins \
    NAGIENT_PROVIDERS_DIR=/var/lib/nagient/providers \
    NAGIENT_CREDENTIALS_DIR=/var/lib/nagient/credentials \
    NAGIENT_STATE_DIR=/var/lib/nagient/state \
    NAGIENT_LOG_DIR=/var/lib/nagient/logs \
    NAGIENT_RELEASES_DIR=/var/lib/nagient/releases \
    NAGIENT_SAFE_MODE=true

WORKDIR /app

COPY pyproject.toml README.md README.ru.md LICENSE /app/
COPY src /app/src
COPY config/nagient.example.toml /etc/nagient/config.toml
COPY config/secrets.example.env /etc/nagient/secrets.env
COPY docker/scripts/entrypoint.sh /usr/local/bin/nagient-entrypoint

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN chmod +x /usr/local/bin/nagient-entrypoint \
    && mkdir -p /var/lib/nagient/config /var/lib/nagient/plugins /var/lib/nagient/providers /var/lib/nagient/credentials /var/lib/nagient/state /var/lib/nagient/logs /var/lib/nagient/releases

VOLUME ["/var/lib/nagient"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -m nagient doctor --format json || exit 1

ENTRYPOINT ["nagient-entrypoint"]
CMD ["nagient", "serve"]
