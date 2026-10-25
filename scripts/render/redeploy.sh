#!/bin/bash

############################################################################
#
#    Agno Render Redeploy
#
#    Usage: ./scripts/render/redeploy.sh
#
#    Triggers a deploy of the agent-os service. Render builds from the
#    connected repo's deploy branch — commit and push your changes first;
#    local uncommitted changes never deploy. (Pushes auto-deploy anyway
#    when autoDeploy is on; this script is for re-running a build without
#    a new commit.)
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
NC='\033[0m'

API="https://api.render.com/v1"
SERVICE_NAME="agent-os"

if ! command -v python3 &> /dev/null; then
    echo "python3 is required (it parses Render API responses)."
    exit 1
fi
render_load_config "$(render_env_file)"
if [[ -z "$RENDER_API_KEY" ]]; then
    echo "RENDER_API_KEY not set (env or env file)."
    exit 1
fi

SERVICE_ID="$(render_resolve_id services service "$SERVICE_NAME" "$RENDER_SERVICE_ID")"
if [[ -z "$SERVICE_ID" ]]; then
    echo "Service '${SERVICE_NAME}' not found. Launch the Blueprint first (./scripts/render/up.sh)."
    exit 1
fi

if [[ -n "$(git status --porcelain 2> /dev/null)" ]]; then
    echo -e "${BOLD}Note:${NC} you have uncommitted changes — Render builds the pushed branch, not your working tree."
fi

echo ""
echo -e "${ORANGE}▸${NC} ${BOLD}Redeploying ${SERVICE_NAME}${NC}"
echo ""
echo -e "${DIM}> POST /services/${SERVICE_ID}/deploys${NC}"
curl -sf -X POST "${API}/services/${SERVICE_ID}/deploys" \
    -H "Authorization: Bearer ${RENDER_API_KEY}" \
    -H 'Content-Type: application/json' -d '{}' > /dev/null

echo ""
echo -e "${BOLD}Done.${NC}"
echo -e "${DIM}Watch it: dashboard.render.com -> ${SERVICE_NAME} -> Events${NC}"
echo ""
