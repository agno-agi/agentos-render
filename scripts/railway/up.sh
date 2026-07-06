#!/bin/bash

############################################################################
#
#    Agno Railway Setup (first-time provisioning)
#
#    Usage:     ./scripts/railway/up.sh
#    Redeploy:  ./scripts/railway/redeploy.sh
#    Sync env:  ./scripts/railway/env-sync.sh
#    Teardown:  ./scripts/railway/down.sh
#
#    Prerequisites:
#      - Railway CLI installed
#      - Logged in via `railway login`
#      - OPENAI_API_KEY set in environment (or .env / .env.production)
#
#    Creates the public domain before deploy, writes it to AGENTOS_URL, and
#    pauses for JWT_VERIFICATION_KEY/JWT_JWKS_FILE when production auth would
#    otherwise prevent the first deploy from serving.
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

# Persist a resolved single-line value back into the env file so it stays a
# faithful record of the deploy (and env-sync.sh keeps managing it). Replaces
# an existing commented-or-uncommented `KEY=` line in place; appends if the key
# is absent. Rewrites via the original file (not `mv`) so the file keeps its
# inode + permissions. The `|` sed delimiter avoids clashing with URL slashes.
# No-op when the file is missing.
persist_env_var() {
    local key="$1" value="$2" file="$3" tmp
    [[ -z "$file" || ! -f "$file" ]] && return
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

# Persist a multi-line env value. Existing active KEY= blocks are removed before
# appending the new value; commented examples are left alone as documentation.
persist_multiline_env_var() {
    local key="$1" value="$2" file="$3" tmp line skipping=0 value_part
    [[ -z "$file" ]] && return
    if [[ ! -f "$file" ]]; then
        printf '%s="%s"\n' "$key" "$value" > "$file"
        return
    fi

    # Values are written quoted so compose's env_file parser (and every script
    # parser here, which strips quotes) reads the multi-line PEM as one variable.
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

# Load env file — .env.production preferred for Railway, .env as fallback.
# Parsed line-by-line (not `source`d) so an unquoted multi-line PEM
# JWT_VERIFICATION_KEY isn't interpreted as shell. Mirrors the parser in
# env-sync.sh so both scripts read .env files identically. A function so
# the JWT pause below can re-read the file after the user edits it.
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

        # Still inside a PEM block — keep accumulating lines.
        if [[ "$current_value" == *"-----BEGIN"* && "$current_value" != *"-----END"* ]]; then
            continue
        fi

        # Strip surrounding quotes if present
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
    local first_line="$1" line pasted="$1"

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

ENV_FILE=""
[[ -f .env.production ]] && ENV_FILE=".env.production"
[[ -z "$ENV_FILE" && -f .env ]] && ENV_FILE=".env"

if [[ -n "$ENV_FILE" ]]; then
    load_env_file "$ENV_FILE"
    echo -e "${DIM}Loaded ${ENV_FILE}${NC}"
fi

# Preflight
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Install: https://docs.railway.app/guides/cli"
    exit 1
fi

if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "OPENAI_API_KEY not set. Add to .env (or .env.production) or export it."
    exit 1
fi

echo -e "${BOLD}Initializing project...${NC}"
echo ""
railway init -n "agentos-railway"

echo ""
echo -e "${BOLD}Deploying PgVector database...${NC}"
echo ""
railway add -s pgvector -i agnohq/pgvector:18 \
    -v "POSTGRES_USER=${DB_USER:-ai}" \
    -v "POSTGRES_PASSWORD=${DB_PASS:-ai}" \
    -v "POSTGRES_DB=${DB_DATABASE:-ai}"

echo ""
echo -e "${BOLD}Adding database volume...${NC}"
railway service link pgvector
railway volume add -m /var/lib/postgresql 2>/dev/null || echo -e "${DIM}Volume already exists or skipped${NC}"

echo ""
echo -e "${DIM}Waiting 15s for database...${NC}"
sleep 15

echo ""
echo -e "${BOLD}Creating application service...${NC}"
echo ""
# Forward every relevant env var the first deploy might need. Optional
# keys are only included when set — Railway CLI rejects empty values.
# Use ./scripts/railway/env-sync.sh to sync the rest from .env later.
RAILWAY_VARS=(
    -v "DB_USER=${DB_USER:-ai}"
    -v "DB_PASS=${DB_PASS:-ai}"
    -v "DB_HOST=pgvector.railway.internal"
    -v "DB_PORT=${DB_PORT:-5432}"
    -v "DB_DATABASE=${DB_DATABASE:-ai}"
    -v "DB_DRIVER=postgresql+psycopg"
    -v "WAIT_FOR_DB=True"
    -v "PORT=8000"
    -v "OPENAI_API_KEY=${OPENAI_API_KEY}"
)
[[ -n "$PARALLEL_API_KEY" ]] && RAILWAY_VARS+=(-v "PARALLEL_API_KEY=${PARALLEL_API_KEY}")
[[ -n "$RUNTIME_ENV" ]] && RAILWAY_VARS+=(-v "RUNTIME_ENV=${RUNTIME_ENV}")
[[ -n "$JWT_JWKS_FILE" ]] && RAILWAY_VARS+=(-v "JWT_JWKS_FILE=${JWT_JWKS_FILE}")
# Forward AGENTOS_URL only if the env file already pinned one; otherwise it's
# derived from the fresh domain below.
[[ -n "$AGENTOS_URL" ]] && RAILWAY_VARS+=(-v "AGENTOS_URL=${AGENTOS_URL}")

railway add -s agent-os "${RAILWAY_VARS[@]}"

# Domain before deploy — capture it so AGENTOS_URL is set on the service
# *before* it serves, and so os.agno.com can mint JWT_VERIFICATION_KEY against
# the real domain.
echo ""
echo -e "${BOLD}Creating domain...${NC}"
echo ""
DOMAIN_OUTPUT="$(railway domain --service agent-os 2>&1 || true)"
echo "$DOMAIN_OUTPUT"
APP_URL="$(grep -oE 'https://[A-Za-z0-9.-]+|[A-Za-z0-9-]+\.up\.railway\.app' <<< "$DOMAIN_OUTPUT" | head -1)"
[[ -n "$APP_URL" && "$APP_URL" != https://* ]] && APP_URL="https://${APP_URL}"

# The scheduler reaches AgentOS over its public URL. Without AGENTOS_URL it
# defaults to http://127.0.0.1:8000, so scheduled jobs silently never fire in
# prod. Default it to the fresh domain (unless the env file pinned one), and
# write it back into the env file so .env.production stays a faithful record
# and env-sync.sh keeps managing it.
AGENTOS_URL_PERSISTED=""
if [[ -z "$AGENTOS_URL" && -n "$APP_URL" ]]; then
    railway variables --set "AGENTOS_URL=${APP_URL}" --service agent-os > /dev/null
    persist_env_var AGENTOS_URL "$APP_URL" "$ENV_FILE"
    [[ -n "$ENV_FILE" ]] && AGENTOS_URL_PERSISTED=1
    echo -e "${DIM}Set AGENTOS_URL=${APP_URL} (Railway${AGENTOS_URL_PERSISTED:+ + ${ENV_FILE}})${NC}"
elif [[ -z "$AGENTOS_URL" ]]; then
    # Domain creation/parse failed and nothing was pinned — don't ship silently
    # with the localhost default, or scheduled jobs will never fire in prod.
    echo -e "${BOLD}Warning:${NC} couldn't determine the Railway domain, so AGENTOS_URL is unset."
    echo -e "${DIM}  Scheduled jobs won't reach AgentOS until you set it. Once the domain is live:${NC}"
    echo -e "${DIM}  railway variables --set AGENTOS_URL=https://<your-domain> --service agent-os${NC}"
    echo -e "${DIM}  (or add it to ${ENV_FILE:-.env.production} and run ./scripts/railway/env-sync.sh)${NC}"
fi

AUTH_REQUIRES_JWT=1
[[ "${RUNTIME_ENV:-prd}" == "dev" ]] && AUTH_REQUIRES_JWT=""

# JWT auth is on in prd and the app refuses to serve without either a PEM
# verification key or a JWKS file. Now that the domain exists, the user can
# mint the key, save it, and have this first deploy come up serving.
if [[ -n "$AUTH_REQUIRES_JWT" && -z "$JWT_VERIFICATION_KEY" && -z "$JWT_JWKS_FILE" && -t 0 ]]; then
    echo ""
    echo -e "${BOLD}JWT_VERIFICATION_KEY not set${NC} — AgentOS won't serve production traffic without auth."
    echo -e "  1. Open ${BOLD}https://os.agno.com${NC} -> Connect OS -> Live -> enter ${APP_URL:-your Railway domain}"
    echo -e "  2. Name it ${BOLD}Live AgentOS${NC}"
    echo -e "  3. Note: Live AgentOS Connections are a paid feature; use ${BOLD}PLATFORM30${NC} to get 1 month off"
    echo -e "  4. Go to Settings -> OS & Security -> turn ${BOLD}Token-Based Authorization (JWT)${NC} on"
    echo -e "  5. Copy the public key"
    echo -e "  6. Paste the full PEM block at the prompt below, or save it in ${ENV_FILE:-.env.production}"
    echo -e "     Or set JWT_JWKS_FILE if you mount a JWKS file in the image."
    [[ -n "$AGENTOS_URL_PERSISTED" ]] && echo -e "  ${DIM}(AGENTOS_URL was already written to ${ENV_FILE} for you.)${NC}"
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
            echo -e "${DIM}  Save it to ${ENV_FILE:-.env.production} and run ./scripts/railway/env-sync.sh if auth is still missing.${NC}"
        fi
    else
        [[ -f .env.production ]] && ENV_FILE=".env.production"
        [[ -z "$ENV_FILE" && -f .env ]] && ENV_FILE=".env"
    fi
    [[ -n "$ENV_FILE" ]] && load_env_file "$ENV_FILE"
fi

if [[ -n "$JWT_VERIFICATION_KEY" ]]; then
    echo ""
    echo -e "${DIM}Setting JWT_VERIFICATION_KEY${NC}"
    railway variables --set "JWT_VERIFICATION_KEY=${JWT_VERIFICATION_KEY}" --service agent-os > /dev/null
elif [[ -n "$JWT_JWKS_FILE" ]]; then
    echo ""
    echo -e "${DIM}Setting JWT_JWKS_FILE=${JWT_JWKS_FILE}${NC}"
    railway variables --set "JWT_JWKS_FILE=${JWT_JWKS_FILE}" --service agent-os > /dev/null
elif [[ -n "$AUTH_REQUIRES_JWT" ]]; then
    echo ""
    echo -e "${DIM}Deploying without JWT auth config — the app will refuse traffic until${NC}"
    echo -e "${DIM}you add JWT_VERIFICATION_KEY or JWT_JWKS_FILE to ${ENV_FILE:-.env.production} and run ./scripts/railway/env-sync.sh.${NC}"
fi

echo ""
echo -e "${BOLD}Deploying application...${NC}"
echo ""
railway up --service agent-os -d

echo ""
echo -e "${BOLD}Done.${NC} The app is building — give it a few minutes."
[[ -n "$APP_URL" ]] && echo -e "${DIM}URL:            ${APP_URL}${NC}"
echo -e "${DIM}Logs:           railway logs --service agent-os${NC}"
echo -e "${DIM}Sync env vars:  ./scripts/railway/env-sync.sh  (defaults to .env.production)${NC}"
echo ""
