#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# ── Bridge ya WhatsApp (Node) — inaendeshwa pamoja na Django na start.sh ──
# Node ikikosekana (au ni ya zamani) tunaipakua kwenye .node/ ya mradi.
NODE_VERSION="$(cat whatsapp_bridge/.node-version 2>/dev/null || echo 22.11.0)"
node_major() { node -v 2>/dev/null | sed 's/^v\([0-9]*\).*/\1/'; }
export PATH="$PWD/.node/bin:$PATH"
if [ "$(node_major || echo 0)" -lt 18 ] 2>/dev/null || ! command -v node >/dev/null 2>&1; then
    echo "Inapakua Node ${NODE_VERSION}..."
    rm -rf .node && mkdir -p .node
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
        | tar -xJ -C .node --strip-components=1
fi
echo "Node $(node -v)"
(cd whatsapp_bridge && npm ci --omit=dev --no-audit --no-fund)
# Data ya sample ya kanuni — inaingizwa TU kama database haina data bado,
# ili deploy isifute data ambayo mteja amepakia kupitia dashboard.
python manage.py import_mhd007 diagnosis/fixtures/mhd007 --if-empty --create-crops
python manage.py import_advisory advisory/fixtures --if-empty --create-crops
