#!/usr/bin/env bash
# Actualiza GEMINI_API_KEY en Coolify vía API y reinicia la app.
# Uso: bash scripts/coolify_set_key.sh   (lee .env.coolify)
set -euo pipefail

cd "$(dirname "$0")/.."
# Parseo manual: los tokens de Coolify llevan "|", que rompe `source`.
while IFS='=' read -r k v; do
  [[ "$k" =~ ^[A-Z_]+$ ]] || continue
  v="${v%$'\r'}"; v="${v#\"}"; v="${v%\"}"
  export "$k=$v"
done < .env.coolify

: "${COOLIFY_URL:?falta COOLIFY_URL}" "${COOLIFY_TOKEN:?falta COOLIFY_TOKEN}"
: "${APP_UUID:?falta APP_UUID}" "${GEMINI_API_KEY:?falta GEMINI_API_KEY}"

API="${COOLIFY_URL%/}/api/v1/applications/$APP_UUID"
AUTH="Authorization: Bearer $COOLIFY_TOKEN"
BODY="{\"key\":\"GEMINI_API_KEY\",\"value\":\"$GEMINI_API_KEY\",\"is_preview\":false}"

echo "1/3 Validando key contra Google..."
code=$(curl -s -o /dev/null -w '%{http_code}' \
  "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY")
[ "$code" = "200" ] || { echo "La key no es válida (HTTP $code)"; exit 1; }

echo "2/3 Actualizando variable en Coolify..."
code=$(curl -s -o /tmp/coolify_resp.txt -w '%{http_code}' -X PATCH "$API/envs" \
  -H "$AUTH" -H "Content-Type: application/json" -d "$BODY")
if [ "$code" != "200" ] && [ "$code" != "201" ]; then
  echo "PATCH devolvió $code, intento crearla (POST)..."
  code=$(curl -s -o /tmp/coolify_resp.txt -w '%{http_code}' -X POST "$API/envs" \
    -H "$AUTH" -H "Content-Type: application/json" -d "$BODY")
  [ "$code" = "200" ] || [ "$code" = "201" ] || { cat /tmp/coolify_resp.txt; echo; exit 1; }
fi

echo "3/3 Reiniciando app..."
curl -s -H "$AUTH" "$API/restart"; echo
echo "Listo."
