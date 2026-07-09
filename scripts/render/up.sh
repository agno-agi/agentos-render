#!/bin/bash

############################################################################
#
#    Agno Render Setup (first-time provisioning, blueprint-guided)
#
#    Usage:     ./scripts/render/up.sh
#    Redeploy:  ./scripts/render/redeploy.sh
#    Sync env:  ./scripts/render/env-sync.sh
#    Teardown:  ./scripts/render/down.sh
#
#    Render provisions from the Blueprint (render.yaml) when you connect
#    the repo — that step happens in the dashboard (or the README's deploy
#    button); Render then builds the Dockerfile and creates the Postgres.
#    This script wraps everything around it: it waits for the service to
#    exist, then pins AGENTOS_URL to the real service URL (a service can't
#    reference its own public URL from render.yaml, and without it
#    scheduled jobs silently never fire), generates MCP_CONNECT_SECRET
#    (chat-app OAuth) into the env file when missing, pauses for the JWT
#    key, and rolls one deploy with the final env.
#
#    Prerequisites:
#      - RENDER_API_KEY set (dashboard.render.com → Account Settings → API Keys),
#        in the environment or the env file
#      - python3 (already required for the repo's eval tooling)
#
############################################################################

set -e

# Colors
ORANGE='\033[38;5;208m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${ORANGE}"
cat << 'BANNER'
     █████╗  ██████╗ ███╗   ██╗ ██████╗
    ██╔══██╗██╔════╝ ████╗  ██║██╔═══██╗
    ███████║██║  ███╗██╔██╗ ██║██║   ██║
    ██╔══██║██║   ██║██║╚██╗██║██║   ██║
    ██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝
    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝
BANNER
echo -e "${NC}"

API="https://api.render.com/v1"
SERVICE_NAME="agent-os"

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

service_id_by_name() {
    api GET "/services?name=${SERVICE_NAME}&limit=20" | python3 -c '
import json, sys
for item in json.load(sys.stdin):
    s = item.get("service", item)
    if s.get("name") == "'"$SERVICE_NAME"'":
        print(s["id"])
        break'
}

service_url() {
    api GET "/services/$1" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("serviceDetails", {}).get("url", ""))'
}

persist_env_var() {
    local key="$1" value="$2" file="$3" tmp
    if [[ -z "$file" ]]; then
        return
    fi
    [[ -f "$file" ]] || touch "$file"
    if grep -qE "^[#[:space:]]*${key}=" "$file"; then
        tmp="$(mktemp)"
        if sed -E "s|^[#[:space:]]*${key}=.*|${key}=${value}|" "$file" > "$tmp"; then
            cat "$tmp" > "$file"
        fi
        rm -f "$tmp"
    else
        printf '\n%s=%s\n' "$key" "$value" >> "$file"
    fi
}

persist_multiline_env_var() {
    local key="$1" value="$2" file="$3" tmp line skipping=0 value_part
    if [[ -z "$file" ]]; then
        return
    fi
    if [[ ! -f "$file" ]]; then
        printf '%s="%s"\n' "$key" "$value" > "$file"
        return
    fi
    tmp="$(mktemp)"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$skipping" == 1 ]]; then
            [[ "$line" == *"-----END"* ]] && skipping=0
            continue
        fi
        if [[ "$line" =~ ^[[:space:]]*${key}= ]]; then
            value_part="${line#*=}"
            if [[ "$value_part" == *"-----BEGIN"* && "$value_part" != *"-----END"* ]]; then
                skipping=1
            fi
            continue
        fi
        printf '%s\n' "$line" >> "$tmp"
    done < "$file"
    [[ -s "$tmp" ]] && printf '\n' >> "$tmp"
    printf '%s="%s"\n' "$key" "$value" >> "$tmp"
    cat "$tmp" > "$file"
    rm -f "$tmp"
}

load_env_file() {
    local line current_key="" current_value=""
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
        export "${current_key}=${current_value}"
        current_key=""
        current_value=""
    done < "$1"
}

capture_pasted_jwt_verification_key() {
    local line pasted="$1"
    pasted="${pasted#export JWT_VERIFICATION_KEY=}"
    pasted="${pasted#JWT_VERIFICATION_KEY=}"
    [[ "$pasted" != *"-----BEGIN"* ]] && return 1
    while [[ "$pasted" != *"-----END"* ]]; do
        if ! IFS= read -r line; then
            break
        fi
        pasted="${pasted}
${line}"
    done
    [[ "$pasted" != *"-----BEGIN"* || "$pasted" != *"-----END"* ]] && return 1
    pasted="${pasted#\"}"
    pasted="${pasted%\"}"
    pasted="${pasted#\'}"
    pasted="${pasted%\'}"
    JWT_VERIFICATION_KEY="$pasted"
    export JWT_VERIFICATION_KEY
}

# Upsert one env var on the service and remember that a deploy is needed.
NEEDS_DEPLOY=""
set_service_env() {
    local sid="$1" key="$2" value="$3"
    python3 -c 'import json,sys; print(json.dumps({"value": sys.argv[1]}))' "$value" \
        | curl -sf -X PUT "${API}/services/${sid}/env-vars/${key}" \
            -H "Authorization: Bearer ${RENDER_API_KEY}" \
            -H 'Content-Type: application/json' -d @- > /dev/null
    NEEDS_DEPLOY=1
}

ENV_FILE=""
[[ -f .env.production ]] && ENV_FILE=".env.production"
[[ -z "$ENV_FILE" && -f .env ]] && ENV_FILE=".env"
if [[ -n "$ENV_FILE" ]]; then
    load_env_file "$ENV_FILE"
    echo -e "${DIM}Loaded ${ENV_FILE}${NC}"
fi

# Preflight
if ! command -v python3 &> /dev/null; then
    echo "python3 is required (it parses Render API responses)."
    exit 1
fi
if [[ -z "$RENDER_API_KEY" ]]; then
    echo "RENDER_API_KEY not set. Create one at dashboard.render.com → Account Settings → API Keys,"
    echo "then export it or add it to ${ENV_FILE:-.env.production}."
    exit 1
fi
if ! api GET "/services?limit=1" > /dev/null; then
    echo "Render API not reachable with this RENDER_API_KEY."
    exit 1
fi

SERVICE_ID="$(service_id_by_name)"
if [[ -z "$SERVICE_ID" ]]; then
    REPO_URL="$(git remote get-url origin 2> /dev/null | sed -E 's|git@github.com:|https://github.com/|; s|\.git$||')"
    echo ""
    echo -e "${ORANGE}▸${NC} ${BOLD}No '${SERVICE_NAME}' service yet${NC} — launch the Blueprint first:"
    echo -e "  1. Open ${BOLD}https://dashboard.render.com/blueprints${NC} -> New Blueprint Instance"
    echo -e "  2. Connect this repo${REPO_URL:+ (${REPO_URL})} — Render reads render.yaml and shows the plan"
    echo -e "  3. It prompts for ${BOLD}OPENAI_API_KEY${NC} (marked sync: false) — paste yours"
    echo -e "  4. Apply. Render builds the Dockerfile and creates the Postgres (~10 min first time)"
    [[ -n "$REPO_URL" ]] && echo -e "  ${DIM}One-click alternative: https://render.com/deploy?repo=${REPO_URL}${NC}"
    echo ""
    echo -e "${ORANGE}▸${NC} ${BOLD}Waiting for the service to appear${NC} ${DIM}(polling every 15s, Ctrl-C to abort)...${NC}"
    for _ in $(seq 1 120); do
        sleep 15
        SERVICE_ID="$(service_id_by_name)"
        [[ -n "$SERVICE_ID" ]] && break
        printf '.'
    done
    echo ""
    if [[ -z "$SERVICE_ID" ]]; then
        echo "Gave up after 30 minutes. Launch the Blueprint, then re-run this script."
        exit 1
    fi
fi
echo -e "${DIM}Service: ${SERVICE_ID}${NC}"

APP_URL="$(service_url "$SERVICE_ID")"
if [[ -z "$APP_URL" ]]; then
    echo "Couldn't read the service URL yet — the first build may still be running."
    echo "Re-run this script once the service shows Live in the dashboard."
    exit 1
fi

# The scheduler reaches AgentOS over its public URL; render.yaml can't
# express "my own URL", so it gets pinned here.
if [[ -z "$AGENTOS_URL" ]]; then
    AGENTOS_URL="$APP_URL"
    set_service_env "$SERVICE_ID" AGENTOS_URL "$AGENTOS_URL"
    ENV_FILE="${ENV_FILE:-.env.production}"
    persist_env_var AGENTOS_URL "$AGENTOS_URL" "$ENV_FILE"
    echo -e "${DIM}Set AGENTOS_URL=${AGENTOS_URL}${NC}"
fi

# MCP OAuth — claude.ai and ChatGPT (web) connect over OAuth only, and the
# consent page is gated by MCP_CONNECT_SECRET, so the user must create the secret manually.
# We generate a secret on behalf of the user when the env file doesn't have one
# (the service URL is guaranteed above, so OAuth has its public origin).
if [[ -z "$MCP_CONNECT_SECRET" ]]; then
    MCP_CONNECT_SECRET="$(openssl rand -base64 32)"
    export MCP_CONNECT_SECRET
    ENV_FILE="${ENV_FILE:-.env.production}"
    persist_env_var MCP_CONNECT_SECRET "$MCP_CONNECT_SECRET" "$ENV_FILE"
    set_service_env "$SERVICE_ID" MCP_CONNECT_SECRET "$MCP_CONNECT_SECRET"
    MCP_SECRET_DELIVERED=1
    echo -e "${DIM}Generated MCP_CONNECT_SECRET -> ${ENV_FILE} + Render (shown in the summary below)${NC}"
fi

AUTH_REQUIRES_JWT=1
[[ "${RUNTIME_ENV:-prd}" == "dev" ]] && AUTH_REQUIRES_JWT=""

if [[ -n "$AUTH_REQUIRES_JWT" && -z "$JWT_VERIFICATION_KEY" && -z "$JWT_JWKS_FILE" && -t 0 ]]; then
    echo ""
    echo -e "${ORANGE}▸${NC} ${BOLD}JWT_VERIFICATION_KEY not set${NC} — AgentOS won't serve production traffic without auth."
    echo -e "  1. Open ${BOLD}https://os.agno.com${NC} -> Connect OS -> Live -> enter ${APP_URL}"
    echo -e "  2. Name it ${BOLD}Live AgentOS${NC}"
    echo -e "  3. Note: Live AgentOS Connections are a paid feature; use ${BOLD}PLATFORM30${NC} to get 1 month off"
    echo -e "  4. Go to Settings -> OS & Security -> turn ${BOLD}Token-Based Authorization (JWT)${NC} on"
    echo -e "  5. Copy the public key"
    echo -e "  6. Paste the full PEM block at the prompt below, or save it in ${ENV_FILE:-.env.production}"
    echo ""
    echo -e "  Paste JWT_VERIFICATION_KEY now, or press Enter after saving it:"
    JWT_INPUT=""
    IFS= read -r JWT_INPUT || true
    if [[ -n "$JWT_INPUT" ]]; then
        if capture_pasted_jwt_verification_key "$JWT_INPUT"; then
            ENV_FILE="${ENV_FILE:-.env.production}"
            persist_multiline_env_var JWT_VERIFICATION_KEY "$JWT_VERIFICATION_KEY" "$ENV_FILE"
            echo -e "${DIM}  Saved JWT_VERIFICATION_KEY to ${ENV_FILE}${NC}"
        else
            echo -e "${BOLD}Warning:${NC} couldn't parse the pasted JWT_VERIFICATION_KEY."
        fi
    fi
    [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] && load_env_file "$ENV_FILE"
fi

if [[ -n "$JWT_VERIFICATION_KEY" ]]; then
    set_service_env "$SERVICE_ID" JWT_VERIFICATION_KEY "$JWT_VERIFICATION_KEY"
    echo -e "${DIM}Set JWT_VERIFICATION_KEY${NC}"
elif [[ -n "$JWT_JWKS_FILE" ]]; then
    set_service_env "$SERVICE_ID" JWT_JWKS_FILE "$JWT_JWKS_FILE"
    echo -e "${DIM}Set JWT_JWKS_FILE=${JWT_JWKS_FILE}${NC}"
elif [[ -n "$AUTH_REQUIRES_JWT" ]]; then
    echo ""
    echo -e "${DIM}No JWT auth config — the app will refuse traffic until you add${NC}"
    echo -e "${DIM}JWT_VERIFICATION_KEY or JWT_JWKS_FILE to ${ENV_FILE:-.env.production} and run ./scripts/render/env-sync.sh.${NC}"
fi

if [[ -n "$NEEDS_DEPLOY" ]]; then
    echo ""
    echo -e "${ORANGE}▸${NC} ${BOLD}Rolling a deploy with the new env${NC}"
    echo ""
    echo -e "${DIM}> POST /services/${SERVICE_ID}/deploys${NC}"
    api POST "/services/${SERVICE_ID}/deploys" '{}' > /dev/null
fi

echo ""
echo -e "${BOLD}Done.${NC}"
echo -e "${DIM}URL:            ${APP_URL}  (docs at /docs, MCP at /mcp)${NC}"
echo -e "${DIM}Logs:           dashboard.render.com -> ${SERVICE_NAME} -> Logs${NC}"
echo -e "${DIM}Sync env vars:  ./scripts/render/env-sync.sh${NC}"
[[ -n "$APP_URL" ]] && echo -e "${DIM}Connect apps:   uvx agno connect --url ${APP_URL}${NC}"
if [[ -n "$APP_URL" && -n "$MCP_CONNECT_SECRET" ]]; then
    echo -e "${DIM}Chat apps:      add ${APP_URL}/mcp as a custom connector in claude.ai / ChatGPT${NC}"
    echo -e "${DIM}                (leave the optional OAuth client ID/secret fields empty).${NC}"
    echo -e "${DIM}                Then click Connect and approve the consent page with this secret:${NC}"
    echo -e "${BOLD}                ${MCP_CONNECT_SECRET}${NC}"
    [[ -z "${MCP_SECRET_DELIVERED:-}" ]] && echo -e "${DIM}                Hand-added secret? run ./scripts/render/env-sync.sh to push it to Render.${NC}"
fi
echo -e "${DIM}Teardown:       ./scripts/render/down.sh${NC}"
echo ""
