FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NAGIENT_HOME=/opt/nagient \
    NAGIENT_CONFIG=/opt/nagient/config.toml \
    NAGIENT_SECRETS_FILE=/opt/nagient/secrets.env \
    NAGIENT_PLUGINS_DIR=/opt/nagient/plugins \
    NAGIENT_PROVIDERS_DIR=/opt/nagient/providers \
    NAGIENT_CREDENTIALS_DIR=/opt/nagient/credentials \
    NAGIENT_STATE_DIR=/opt/nagient/state \
    NAGIENT_LOG_DIR=/opt/nagient/logs \
    NAGIENT_RELEASES_DIR=/opt/nagient/releases \
    NAGIENT_SAFE_MODE=true

WORKDIR /app

COPY pyproject.toml README.md README.ru.md LICENSE /app/
COPY src /app/src
COPY config/nagient.example.toml /etc/nagient/config.toml
COPY config/secrets.example.env /etc/nagient/secrets.env
COPY docker/scripts/entrypoint.sh /usr/local/bin/nagient-entrypoint

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        iputils-ping \
        procps \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN chmod +x /usr/local/bin/nagient-entrypoint \
    && mkdir -p /opt/nagient/plugins /opt/nagient/providers /opt/nagient/credentials /opt/nagient/state /opt/nagient/logs /opt/nagient/releases

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -m nagient doctor --format json || exit 1

ENTRYPOINT ["nagient-entrypoint"]
CMD ["nagient", "serve"]
