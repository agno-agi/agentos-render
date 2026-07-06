#!/bin/bash

############################################################################
#
#    Agno Railway Redeploy
#
#    Usage: ./scripts/railway/redeploy.sh
#
#    Redeploys the agent-os app service to an existing Railway project.
#    Run ./scripts/railway/up.sh first for initial provisioning.
#
############################################################################

set -e

# Colors
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

# Preflight
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Install: https://docs.railway.com/cli#installing-the-cli"
    exit 1
fi

if ! railway status &> /dev/null; then
    echo "Not linked to a Railway project. Run ./scripts/railway/up.sh first."
    exit 1
fi

echo ""
echo -e "${BOLD}Redeploying agent-os...${NC}"
echo ""
railway up --service agent-os -d

echo ""
echo -e "${BOLD}Done.${NC}"
echo -e "${DIM}Logs: railway logs --service agent-os${NC}"
echo ""
