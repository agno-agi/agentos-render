#!/bin/bash

############################################################################
#
#    Agno Render Environment Sync
#
#    Usage:
#      ./scripts/render/env-sync.sh             # syncs .env.production
#      ./scripts/render/env-sync.sh .env        # syncs .env instead
#
#    Reads the env file and upserts every variable onto the agent-os
#    service (one PUT per key — never the destructive replace-all call),
#    pins AGENTOS_URL to the live service URL if the file doesn't carry
#    one, then rolls one deploy to apply. Multi-line values (PEM-formatted
#    JWT_VERIFICATION_KEY) are handled correctly. RENDER_* keys are
#    skipped (script config, not app env).
#
#    Prerequisites: RENDER_API_KEY (env or env file), python3.
#
############################################################################

set -e

# Colors
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

API="https://api.render.com/v1"
SERVICE_NAME="agent-os"
ENV_FILE="${1:-.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "File not found: $ENV_FILE"
    echo "Usage: $0 [path/to/env] (default: .env.production)"
    exit 1
fi
if ! command -v python3 &> /dev/null; then
    echo "python3 is required (it parses Render API responses)."
    exit 1
fi

# RENDER_API_KEY may live in the env file itself.
if [[ -z "$RENDER_API_KEY" ]]; then
    RENDER_API_KEY="$(sed -nE 's/^RENDER_API_KEY=(.*)$/\1/p' "$ENV_FILE" | head -1)"
fi
if [[ -z "$RENDER_API_KEY" ]]; then
    echo "RENDER_API_KEY not set (env or ${ENV_FILE})."
    exit 1
fi

api() {
    local method="$1" path="$2" body="${3:-}"
    if [[ -n "$body" ]]; then
        curl -sf -X "$method" "${API}${path}" \
            -H "Authorization: Bearer ${RENDER_API_KEY}" \
            -H 'Content-Type: application/json' -d "$body"
    else
        curl -sf -X "$method" "${API}${path}" \
            -H "Authorization: Bearer ${RENDER_API_KEY}"
    fi
}

SERVICE_ID="$(api GET "/services?name=${SERVICE_NAME}&limit=20" | python3 -c '
import json, sys
for item in json.load(sys.stdin):
    s = item.get("service", item)
    if s.get("name") == "'"$SERVICE_NAME"'":
        print(s["id"])
        break')"
if [[ -z "$SERVICE_ID" ]]; then
    echo "Service '${SERVICE_NAME}' not found. Launch the Blueprint first (./scripts/render/up.sh)."
    exit 1
fi

set_service_env() {
    local key="$1" value="$2"
    python3 -c 'import json,sys; print(json.dumps({"value": sys.argv[1]}))' "$value" \
        | curl -sf -X PUT "${API}/services/${SERVICE_ID}/env-vars/${key}" \
            -H "Authorization: Bearer ${RENDER_API_KEY}" \
            -H 'Content-Type: application/json' -d @- > /dev/null
}

echo ""
echo -e "${BOLD}Syncing env vars from ${ENV_FILE} to ${SERVICE_NAME}...${NC}"
echo ""

count=0
saw_agentos_url=""
current_key=""
current_value=""

while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ -z "$current_key" ]]; then
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    fi

    if [[ -z "$current_key" ]]; then
        current_key="${line%%=*}"
        current_value="${line#*=}"
    else
        current_value="${current_value}
${line}"
    fi

    if [[ "$current_value" == *"-----BEGIN"* && "$current_value" != *"-----END"* ]]; then
        continue
    fi

    current_value="${current_value#\"}"
    current_value="${current_value%\"}"
    current_value="${current_value#\'}"
    current_value="${current_value%\'}"

    case "$current_key" in
        RENDER_*)
            # Script config, not app environment.
            ;;
        *)
            [[ "$current_key" == "AGENTOS_URL" ]] && saw_agentos_url=1
            echo -e "${DIM}  Setting ${current_key}${NC}"
            set_service_env "$current_key" "$current_value"
            count=$((count + 1))
            ;;
    esac

    current_key=""
    current_value=""
done < "$ENV_FILE"

# No AGENTOS_URL in the file — pin it to the live URL so scheduled jobs fire.
if [[ -z "$saw_agentos_url" ]]; then
    APP_URL="$(api GET "/services/${SERVICE_ID}" | python3 -c '
import json, sys
print(json.load(sys.stdin).get("serviceDetails", {}).get("url", ""))')"
    if [[ -n "$APP_URL" ]]; then
        echo -e "${DIM}  Setting AGENTOS_URL=${APP_URL}${NC}"
        set_service_env AGENTOS_URL "$APP_URL"
        count=$((count + 1))
    fi
fi

echo ""
echo -e "${BOLD}Rolling a deploy to apply...${NC}"
api POST "/services/${SERVICE_ID}/deploys" '{}' > /dev/null

echo ""
echo -e "${BOLD}Done.${NC} Synced ${count} variable(s)."
echo ""
