#!/bin/sh
# Запуск обоих серверов разработки: сервер анализа речи и сервер приложения.
# Настройки берутся из .env, если он есть. ANALYSIS_INPROCESS=1 оставляет один процесс.
cd "$(dirname "$0")" || exit 1
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "$ANALYSIS_URL" ] && [ "$ANALYSIS_INPROCESS" != "1" ]; then
    .venv/bin/python analysis_wsgi.py &
    ANALYSIS_PID=$!
    trap 'kill $ANALYSIS_PID 2>/dev/null' EXIT INT TERM
    export ANALYSIS_URL="http://127.0.0.1:${ANALYSIS_PORT:-5051}"
fi
.venv/bin/python wsgi.py
