#!/usr/bin/env bash
set -euo pipefail

NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
PURGE="${NAGIENT_PURGE:-false}"

if [ -f "$NAGIENT_COMPOSE_FILE" ]; then
  docker compose -f "$NAGIENT_COMPOSE_FILE" --env-file "$NAGIENT_ENV_FILE" down --remove-orphans || true
fi

if [ "$PURGE" = "true" ]; then
  rm -rf "$NAGIENT_HOME"
  echo "Nagient removed with local state purge."
else
  echo "Containers removed. Local files kept in ${NAGIENT_HOME}."
fi

