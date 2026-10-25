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
#    with the exact-resource checks this script runs for you.
#
#    Prerequisites: RENDER_API_KEY (env or env file), python3.
#
############################################################################

set -e -o pipefail

source "$(dirname "${BASH_SOURCE[0]}")/resources.sh"

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
render_load_config "$(render_env_file)"
if [[ -z "$RENDER_API_KEY" ]]; then
    echo "RENDER_API_KEY not set (env or env file)."
    exit 1
fi

api() {
    local method="$1" path="$2"
    curl -sf -X "$method" "${API}${path}" \
        -H "Authorization: Bearer ${RENDER_API_KEY}"
}

SERVICE_ID="$(render_resolve_id services service "$SERVICE_NAME" "$RENDER_SERVICE_ID")"
DB_ID="$(render_resolve_id postgres postgres "$DB_NAME" "$RENDER_POSTGRES_ID")"

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

# Verify the exact selected resources. Auth/network failures are not absence.
render_verify_deleted services "$SERVICE_ID"
render_verify_deleted postgres "$DB_ID"

echo ""
echo -e "${BOLD}Done.${NC} Service and database confirmed gone."
echo -e "${DIM}The Blueprint instance itself can be removed in the dashboard (Blueprints tab).${NC}"
echo ""
