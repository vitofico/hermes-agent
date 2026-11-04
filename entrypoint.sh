#!/bin/bash
set -euo pipefail

export PATH="/opt/hermes/.venv/bin:$PATH"
export HOME="${HOME:-/opt/data}"
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export HERMES_WRITE_SAFE_ROOT="${HERMES_WRITE_SAFE_ROOT:-$HOME}"
# Keep the original single-user variable as a migration alias.
export TELEGRAM_ALLOWED_USERS="${TELEGRAM_ALLOWED_USERS:-${TELEGRAM_USER_ID:-}}"
export WEBHOOK_SECRET="${WEBHOOK_SECRET:-${HERMES_WEBHOOK_SECRET:-}}"
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -z "$TELEGRAM_ALLOWED_USERS" ]]; then
    echo 'TELEGRAM_ALLOWED_USERS is required when Telegram is enabled' >&2
    exit 1
fi
if [[ "${WEBHOOK_ENABLED:-false}" == true && -z "$WEBHOOK_SECRET" ]]; then
    echo 'WEBHOOK_SECRET is required when webhooks are enabled' >&2
    exit 1
fi
umask 077
mkdir -p "$HERMES_HOME"
# Secrets stay in the inherited environment; do not persist a generated .env.
# Let Hermes manage its own PID file and lock, including stale PID recovery.
exec hermes gateway run
