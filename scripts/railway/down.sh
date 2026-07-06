#!/bin/bash

############################################################################
#
#    Agno Railway Teardown
#
#    Usage:
#      ./scripts/railway/down.sh          # asks before destroying
#      ./scripts/railway/down.sh --yes    # no prompt (CI / automation)
#
#    Deletes the linked Railway project — the agent-os service, the
#    pgvector database, and its volume. All data in the database is
#    deleted. Run from the repo root. Verify afterwards with
#    `railway list`.
#
############################################################################

set -e

# Colors
DIM='\033[2m'
BOLD='\033[1m'
RED='\033[31m'
NC='\033[0m'

# Preflight
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Install: https://docs.railway.com/cli#installing-the-cli"
    exit 1
fi

if ! railway whoami &> /dev/null; then
    echo "Not logged in to Railway. Run: railway login"
    exit 1
fi

if ! railway status &> /dev/null; then
    echo "Not linked to a Railway project — nothing to tear down."
    echo "Run this from the directory ./scripts/railway/up.sh deployed from, or check: railway list"
    exit 1
fi

# Identify the linked project. `railway status --json` returns the project
# object, so its first "id"/"name" are the project's own (service and
# environment ids are nested deeper). Fragments are split on ',' and '{'
# first because a greedy sed over one long JSON line would match the LAST
# occurrence, not the first.
STATUS_JSON="$(railway status --json 2> /dev/null)"
PROJECT_ID="$(tr ',{' '\n' <<< "$STATUS_JSON" | sed -nE 's/.*"id": *"([^"]+)".*/\1/p' | head -1)"
PROJECT_NAME="$(tr ',{' '\n' <<< "$STATUS_JSON" | sed -nE 's/.*"name": *"([^"]+)".*/\1/p' | head -1)"

if [[ -z "$PROJECT_ID" || -z "$PROJECT_NAME" ]]; then
    echo "Couldn't read the linked project from 'railway status --json'."
    echo "Delete it manually with 'railway delete' or from the Railway dashboard."
    exit 1
fi

echo ""
echo -e "${BOLD}This deletes the Railway project:${NC}"
echo -e "  - project   ${PROJECT_NAME}  ${DIM}(${PROJECT_ID})${NC}"
echo -e "  - services  agent-os + pgvector  ${RED}(all data deleted)${NC}"
echo ""

if [[ "$1" != "--yes" ]]; then
    printf "Type the project name (%s) to confirm: " "$PROJECT_NAME"
    IFS= read -r CONFIRM
    if [[ "$CONFIRM" != "$PROJECT_NAME" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo ""
echo -e "${BOLD}Deleting ${PROJECT_NAME}...${NC}"
railway delete --project "$PROJECT_ID" --yes \
    || echo -e "${DIM}Delete returned non-zero — verifying below${NC}"

# The project only counts as gone when Railway no longer lists it. `railway
# list` also fails on an expired token or a network blip — treating that as
# "gone" would unlink the directory while the project (and its database)
# is still alive and billing.
if ! LIST_JSON="$(railway list --json 2>&1)"; then
    echo ""
    echo -e "${BOLD}Couldn't verify the project is gone${NC} — railway list failed with:"
    echo -e "${DIM}${LIST_JSON}${NC}"
    echo "The directory stays linked so you can retry. Check: railway list"
    exit 1
fi

if grep -qF "$PROJECT_ID" <<< "$LIST_JSON"; then
    echo ""
    echo -e "${BOLD}Teardown incomplete${NC} — the project is still listed. Retry, or if your"
    echo -e "account has 2FA enabled, delete needs a code in non-interactive mode:"
    echo -e "${DIM}  railway delete --project ${PROJECT_ID} --yes --2fa-code <code>${NC}"
    exit 1
fi

# A Railway-minted domain dies with the project. Comment it out of the env
# file(s) so a future up.sh derives the fresh domain instead of pinning the
# dead one; custom domains are left alone.
for f in .env.production .env; do
    if [[ -f "$f" ]] && grep -qE '^AGENTOS_URL=.*\.up\.railway\.app/?$' "$f"; then
        sed -i.bak -E 's|^(AGENTOS_URL=.*\.up\.railway\.app/?)$|# \1|' "$f" && rm -f "$f.bak"
        echo -e "${DIM}Commented out the stale AGENTOS_URL in ${f}${NC}"
    fi
done

# Only unlink once the project is confirmed gone — unlinking after a failed
# delete would leave the resources running with no local record of them.
railway unlink --yes &> /dev/null || true

echo ""
echo -e "${BOLD}Done.${NC} Project confirmed gone and directory unlinked. Verify anytime with: railway list"
echo ""
