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
#    Once both are confirmed gone, comments the two settings that died with
#    them out of .env.production / .env — the Render-minted AGENTOS_URL and
#    the JWT_VERIFICATION_KEY — so the next up.sh pins the fresh service URL
#    and re-runs its guided key step.
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

# Comment out a KEY= block, PEM continuation lines included, and stamp the
# reason above it. Commenting only the first line of a multi-line value is worse
# than leaving it: up.sh's env parser skips the commented `KEY="-----BEGIN...`
# line and then reads the next base64 line as a key name of its own. Rewrites
# through the original file (not `mv`) so it keeps its inode and permissions.
# Returns 1 when there was no active block to comment.
comment_out_env_block() {
    local key="$1" file="$2" tmp line commenting=0 hit=0 value_part reason
    shift 2
    [[ -f "$file" ]] || return 1
    grep -qE "^[[:space:]]*${key}=" "$file" || return 1

    tmp="$(mktemp)"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$commenting" == 1 ]]; then
            printf '# %s\n' "$line" >> "$tmp"
            [[ "$line" == *"-----END"* ]] && commenting=0
            continue
        fi
        if [[ "$line" =~ ^[[:space:]]*${key}= ]]; then
            hit=1
            for reason in "$@"; do
                printf '# %s\n' "$reason" >> "$tmp"
            done
            printf '# %s\n' "$line" >> "$tmp"
            value_part="${line#*=}"
            if [[ "$value_part" == *"-----BEGIN"* && "$value_part" != *"-----END"* ]]; then
                commenting=1
            fi
            continue
        fi
        printf '%s\n' "$line" >> "$tmp"
    done < "$file"

    cat "$tmp" > "$file"
    rm -f "$tmp"
    [[ "$hit" == 1 ]]
}

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

# An onrender.com URL dies with the service, and the next Blueprint launch mints
# a new one. Comment the dead value out of the env file(s) so a future up.sh
# pins the fresh URL instead of keeping the corpse: left in place it short-
# circuits up.sh's pin step and makes env-sync.sh push the dead domain — the
# unset-AGENTOS_URL failure mode where scheduled jobs silently never fire and
# MCP OAuth advertises an origin nobody serves. Custom domains are left alone.
#
# JWT_VERIFICATION_KEY goes with it. It belongs to the os.agno.com OS connection
# that pointed at the service just deleted, and up.sh's guided key step is gated
# on the variable being absent — left in place it silently skips, and the next
# deploy comes up verifying tokens against a connection nobody is minting them
# from. Commenting it costs one paste; leaving it costs a platform that refuses
# every request.
for f in .env.production .env; do
    [[ -f "$f" ]] || continue
    if grep -qE '^AGENTOS_URL=.*\.onrender\.com/?$' "$f"; then
        sed -i.bak -E 's|^(AGENTOS_URL=.*\.onrender\.com/?)$|# \1|' "$f" && rm -f "$f.bak"
        echo -e "${DIM}Commented out the stale AGENTOS_URL in ${f}${NC}"
    fi
    if comment_out_env_block JWT_VERIFICATION_KEY "$f" \
        "Commented out by scripts/render/down.sh — minted at os.agno.com for the" \
        "deployment just deleted. up.sh will walk you through a fresh key; uncomment" \
        "this instead if you point the same OS connection at the new service URL."; then
        echo -e "${DIM}Commented out the stale JWT_VERIFICATION_KEY in ${f}${NC}"
    fi
done

echo ""
echo -e "${BOLD}Done.${NC} Service and database confirmed gone."
echo -e "${DIM}The Blueprint instance itself can be removed in the dashboard (Blueprints tab).${NC}"
echo ""
