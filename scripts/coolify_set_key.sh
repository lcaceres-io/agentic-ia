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
# Se prueba con generateContent: el listado de modelos responde 200 aun con proyectos bloqueados.
MODELO_TEST="${GEMINI_MODEL:-gemini-3.1-flash-lite}"
code=$(curl -s -o /tmp/gemini_test.txt -w '%{http_code}' -H 'Content-Type: application/json' \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -d '{"contents":[{"parts":[{"text":"hola"}]}]}' \
  "https://generativelanguage.googleapis.com/v1beta/models/$MODELO_TEST:generateContent")
[ "$code" = "200" ] || { echo "La key no responde (HTTP $code)"; head -c 400 /tmp/gemini_test.txt; echo; exit 1; }

echo "2/3 Actualizando variable en Coolify..."
code=$(curl -s -o /tmp/coolify_resp.txt -w '%{http_code}' -X PATCH "$API/envs" \
  -H "$AUTH" -H "Content-Type: application/json" -d "$BODY")
if [ "$code" != "200" ] && [ "$code" != "201" ]; then
  echo "PATCH devolvió $code, intento crearla (POST)..."
  code=$(curl -s -o /tmp/coolify_resp.txt -w '%{http_code}' -X POST "$API/envs" \
    -H "$AUTH" -H "Content-Type: application/json" -d "$BODY")
  [ "$code" = "200" ] || [ "$code" = "201" ] || { cat /tmp/coolify_resp.txt; echo; exit 1; }
fi

if [ -n "${GEMINI_MODEL:-}" ]; then
  echo "    + GEMINI_MODEL=$GEMINI_MODEL"
  curl -s -o /dev/null -X PATCH "$API/envs" -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"key\":\"GEMINI_MODEL\",\"value\":\"$GEMINI_MODEL\",\"is_preview\":false}"
fi

echo "3/3 Desplegando app..."
curl -s -H "$AUTH" "${COOLIFY_URL%/}/api/v1/deploy?uuid=$APP_UUID&force=false"; echo
echo "Listo."
