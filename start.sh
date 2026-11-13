#!/usr/bin/env bash
# =====================================================================
# Kilimoni AI — web service MOJA: Django + bridge ya WhatsApp (Baileys)
# =====================================================================
#
#   Render ($PORT, umma)  ──>  gunicorn (Django)
#                                   │  BRIDGE_URL=http://127.0.0.1:3001
#                                   ▼
#                      bridge ya Node (127.0.0.1:3001, ndani tu)
#                                   │  DJANGO_URL=http://127.0.0.1:$PORT
#                                   ▼
#                               WhatsApp
#
# - Bridge haina URL ya umma: inasikiliza 127.0.0.1 tu; Django ndiyo
#   inayoiongelesha (Dashboard → WhatsApp).
# - Bridge ikianguka inawashwa upya yenyewe (kitanzi hapa chini).
# - Session ya WhatsApp iko Supabase (baileys_auth): deploy/restart
#   haihitaji kuscan QR upya.
# - RUN_BRIDGE=0 → Django peke yake (mf. bridge iko service nyingine).
set -u
cd "$(dirname "$0")"

export PATH="$PWD/.node/bin:$PATH"
PORT="${PORT:-8000}"
WEB_PORT="$PORT"          # port ya Django (bridge inaiita hapa)
BRIDGE_PORT="${BRIDGE_PORT:-3001}"
RUN_BRIDGE="${RUN_BRIDGE:-1}"

if [ "$RUN_BRIDGE" = "1" ]; then
    export BRIDGE_URL="http://127.0.0.1:${BRIDGE_PORT}"

    # Ufunguo wa ndani kati ya Django na bridge. Ukiwa haujawekwa,
    # tunatengeneza mmoja kwa kila kuanza — process zote mbili zinaurithi.
    if [ -z "${BRIDGE_API_KEY:-}" ]; then
        export BRIDGE_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    fi

    # Bridge inahitaji DATABASE_URL; Django inatumia DB_*. Tunaijenga kutoka
    # mipangilio ileile ya Django (decouple: env au .env) ikiwa haipo.
    if [ -z "${DATABASE_URL:-}" ]; then
        DATABASE_URL="$(python - <<'PY'
from urllib.parse import quote
from decouple import config
user = config('DB_USER', default='')
if user:
    print(f"postgresql://{quote(user, safe='')}:{quote(config('DB_PASSWORD', default=''), safe='')}"
          f"@{config('DB_HOST', default='localhost')}:{config('DB_PORT', default='5432')}"
          f"/{config('DB_NAME', default='postgres')}")
PY
)"
        export DATABASE_URL
    fi

    if [ -z "${DATABASE_URL:-}" ]; then
        echo "[start] DATABASE_URL/DB_* haipo — bridge haiwezi kuhifadhi session; inaachwa."
    elif ! command -v node >/dev/null 2>&1 || [ ! -d whatsapp_bridge/node_modules ]; then
        echo "[start] Node au node_modules za bridge hazipo (build.sh) — bridge inaachwa."
    else
        (
            cd whatsapp_bridge
            delay=3
            while true; do
                started=$(date +%s)
                echo "[start] bridge inaanza (127.0.0.1:${BRIDGE_PORT})"
                PORT="$BRIDGE_PORT" BRIDGE_HOST=127.0.0.1 \
                DJANGO_URL="http://127.0.0.1:${WEB_PORT}" \
                PG_POOL_MAX="${PG_POOL_MAX:-3}" \
                node --max-old-space-size="${BRIDGE_MAX_MB:-256}" server.js
                code=$?
                # ilidumu zaidi ya dakika 5 → ilikuwa nzima; anza upya haraka
                [ $(( $(date +%s) - started )) -gt 300 ] && delay=3
                echo "[start] bridge imesimama (code $code) — inawashwa upya baada ya ${delay}s"
                sleep "$delay"
                delay=$(( delay * 2 > 60 ? 60 : delay * 2 ))
            done
        ) &
    fi
fi

# worker 1 + threads: Django na bridge zinashiriki RAM ya service moja.
# Foleni ya jumbe (whatsapp_incomingmessage) inashughulikia mpangilio.
exec gunicorn mkulima_ai.wsgi:application \
    --bind "0.0.0.0:${WEB_PORT}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 120
