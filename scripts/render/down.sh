#!/bin/bash

############################################################################
#
#    Agno Render Teardown
#
#    Usage:
#      ./scripts/render/down.sh          # asks before destroying
#      ./scripts/render/down.sh --yes    # no prompt (CI / automation)
#
#    Deletes the agent-os service AND the agentos-db Postgres — all data
#    in the database is deleted. Verify afterwards in the dashboard or
#    with the list calls this script runs for you.
#
#    Prerequisites: RENDER_API_KEY (env or env file), python3.
#
############################################################################

set -e

# Colors
ORANGE='\033[38;5;208m'
DIM='\033[2m'
BOLD='\033[1m'
RED='\033[31m'
NC='\033[0m'

API="https://api.render.com/v1"
SERVICE_NAME="agent-os"
DB_NAME="agentos-db"

if ! command -v python3 &> /dev/null; then
    echo "python3 is required (it parses Render API responses)."
    exit 1
fi
if [[ -z "$RENDER_API_KEY" ]]; then
    for f in .env.production .env; do
        if [[ -f "$f" ]]; then
            RENDER_API_KEY="$(sed -nE 's/^RENDER_API_KEY=(.*)$/\1/p' "$f" | head -1)"
            [[ -n "$RENDER_API_KEY" ]] && break
        fi
    done
fi
if [[ -z "$RENDER_API_KEY" ]]; then
    echo "RENDER_API_KEY not set (env or env file)."
    exit 1
fi

api() {
    local method="$1" path="$2"
    curl -sf -X "$method" "${API}${path}" \
        -H "Authorization: Bearer ${RENDER_API_KEY}"
}

first_id_by_name() {
    # stdin: a Render list response; $1: wrapper key; $2: name to match
    python3 -c '
import json, sys
for item in json.load(sys.stdin):
    o = item.get(sys.argv[1], item)
    if o.get("name") == sys.argv[2]:
        print(o["id"])
        break' "$1" "$2"
}

SERVICE_ID="$(api GET "/services?name=${SERVICE_NAME}&limit=20" | first_id_by_name service "$SERVICE_NAME")"
DB_ID="$(api GET "/postgres?name=${DB_NAME}&limit=20" | first_id_by_name postgres "$DB_NAME")"

if [[ -z "$SERVICE_ID" && -z "$DB_ID" ]]; then
    echo "Nothing to tear down — no '${SERVICE_NAME}' service or '${DB_NAME}' database found."
    exit 1
fi

echo ""
echo -e "${ORANGE}▸${NC} ${BOLD}Render Teardown${NC}"
echo ""
echo -e "This deletes:"
[[ -n "$SERVICE_ID" ]] && echo -e "  - service   ${SERVICE_NAME}  ${DIM}(${SERVICE_ID})${NC}"
[[ -n "$DB_ID" ]] && echo -e "  - postgres  ${DB_NAME}  ${DIM}(${DB_ID})${NC}  ${RED}(all data deleted)${NC}"
echo ""

if [[ "$1" != "--yes" ]]; then
    printf "Type the service name (%s) to confirm: " "$SERVICE_NAME"
    IFS= read -r CONFIRM
    if [[ "$CONFIRM" != "$SERVICE_NAME" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

if [[ -n "$SERVICE_ID" ]]; then
    echo ""
    echo -e "${DIM}> DELETE /services/${SERVICE_ID}${NC}"
    api DELETE "/services/${SERVICE_ID}" > /dev/null \
        || echo -e "${DIM}Delete returned non-zero — verifying below${NC}"
fi
if [[ -n "$DB_ID" ]]; then
    echo ""
    echo -e "${DIM}> DELETE /postgres/${DB_ID}${NC}"
    api DELETE "/postgres/${DB_ID}" > /dev/null \
        || echo -e "${DIM}Delete returned non-zero — verifying below${NC}"
fi

# Gone only when the API no longer lists them — an auth/network blip during
# delete must not read as a clean teardown.
LEFT_SERVICE="$(api GET "/services?name=${SERVICE_NAME}&limit=20" | first_id_by_name service "$SERVICE_NAME")"
LEFT_DB="$(api GET "/postgres?name=${DB_NAME}&limit=20" | first_id_by_name postgres "$DB_NAME")"
if [[ -n "$LEFT_SERVICE" || -n "$LEFT_DB" ]]; then
    echo ""
    echo -e "${RED}${BOLD}Teardown incomplete${NC} — still listed:"
    [[ -n "$LEFT_SERVICE" ]] && echo "  service ${LEFT_SERVICE}"
    [[ -n "$LEFT_DB" ]] && echo "  postgres ${LEFT_DB}"
    exit 1
fi

echo ""
echo -e "${BOLD}Done.${NC} Service and database confirmed gone."
echo -e "${DIM}The Blueprint instance itself can be removed in the dashboard (Blueprints tab).${NC}"
echo ""
