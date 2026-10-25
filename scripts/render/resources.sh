#!/bin/bash
# Shared resource targeting for the Render scripts. Never source an env file.

render_env_file() {
    if [[ -f .env.production ]]; then printf '%s' .env.production
    elif [[ -f .env ]]; then printf '%s' .env
    fi
}

render_load_config() {
    local file="$1" key value
    for key in RENDER_API_KEY RENDER_SERVICE_ID RENDER_POSTGRES_ID; do
        # Explicit process settings take precedence over the selected file.
        [[ -n "${!key}" ]] && continue
        value="$(python3 - "$file" "$key" <<'PY'
import pathlib, shlex, sys
path = pathlib.Path(sys.argv[1])
value = ""
if path.is_file():
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        key, sep, raw = line.partition("=")
        if sep and key.strip() == sys.argv[2]:
            parts = shlex.split(raw, comments=True)
            if len(parts) > 1:
                raise SystemExit("Invalid Render setting: " + key)
            value = parts[0] if parts else ""
print(value)
PY
)" || return 1
        export "${key}=${value}"
    done
}

render_resolve_id() {
    local collection="$1" wrapper="$2" name="$3" explicit="$4" response path
    if [[ -n "$explicit" ]]; then
        [[ "$explicit" =~ ^[a-zA-Z0-9-]+$ ]] || { echo "Invalid Render resource ID." >&2; return 1; }
        path="/${collection}/${explicit}"
    else
        path="/${collection}?name=${name}&limit=20"
    fi
    response="$(curl -sf "${API}${path}" -H "Authorization: Bearer ${RENDER_API_KEY}")" || {
        echo "Cannot verify Render ${collection}; check account access and connectivity." >&2
        return 1
    }
    printf '%s' "$response" | python3 -c '
import json, sys
wrapper, name, explicit = sys.argv[1:]
data = json.load(sys.stdin)
if explicit:
    resource = data.get(wrapper, data)
    if resource.get("id") != explicit or resource.get("name") != name:
        raise SystemExit("Render resource ID does not match the expected " + name)
    print(explicit)
else:
    if not isinstance(data, list) or len(data) >= 20:
        raise SystemExit("Render lookup may be truncated; set an explicit resource ID.")
    resources = [item.get(wrapper, item) for item in data]
    if any(not isinstance(item, dict) or not item.get("id") or not item.get("name") for item in resources):
        raise SystemExit("Invalid Render resource lookup response.")
    matches = [item["id"] for item in resources if item["name"] == name]
    if len(matches) > 1:
        raise SystemExit("Ambiguous Render resource name; set an explicit resource ID.")
    if matches:
        print(matches[0])
' "$wrapper" "$name" "$explicit"
}

render_verify_deleted() {
    local collection="$1" id="$2" status
    [[ -z "$id" ]] && return 0
    status="$(curl -sS -o /dev/null -w '%{http_code}' "${API}/${collection}/${id}" \
        -H "Authorization: Bearer ${RENDER_API_KEY}")" || return 1
    if [[ "$status" != 404 ]]; then
        echo "Cannot confirm deletion of ${id} (HTTP ${status})." >&2
        return 1
    fi
}
