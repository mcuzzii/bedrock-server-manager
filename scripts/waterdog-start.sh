#!/bin/sh
set -eu

echo "======================================"
echo " WaterdogPE for playit (Endstone backend)"
echo "======================================"

: "${NETHERNET_TOKEN:?NETHERNET_TOKEN is missing}"
BACKEND_ADDRESS="${BACKEND_ADDRESS:-127.0.0.1:19142}"
export BACKEND_ADDRESS

mkdir -p /waterdog
cd /waterdog

# Tools (only installed if missing, so restarts are fast)
if ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import yaml' 2>/dev/null; then
    apt-get update
    apt-get install -y --no-install-recommends curl ca-certificates python3 python3-yaml
    rm -rf /var/lib/apt/lists/*
fi

# Download WaterdogPE if missing
if [ ! -s Waterdog.jar ]; then
    echo "Downloading WaterdogPE..."
    DOWNLOAD_URL=$(
        curl -fsSL https://api.github.com/repos/WaterdogPE/WaterdogPE/releases/latest |
        python3 -c '
import json, sys
data = json.load(sys.stdin)
assets = [a["browser_download_url"] for a in data.get("assets", []) if a["name"].endswith(".jar")]
if not assets:
    sys.exit("No JAR asset found")
print(assets[0])
'
    )
    curl -fL "$DOWNLOAD_URL" -o Waterdog.jar
fi

# Generate the default config.yml once
if [ ! -s config.yml ]; then
    echo "Generating default WaterdogPE configuration..."
    java -jar Waterdog.jar &
    INIT_PID=$!
    for i in $(seq 1 60); do
        [ -s config.yml ] && break
        if ! kill -0 "$INIT_PID" 2>/dev/null; then
            echo "WaterdogPE exited before generating config.yml"; exit 1
        fi
        sleep 1
    done
    if [ ! -s config.yml ]; then
        kill "$INIT_PID" 2>/dev/null || true
        echo "Failed to generate config.yml"; exit 1
    fi
    kill "$INIT_PID" 2>/dev/null || true
    wait "$INIT_PID" 2>/dev/null || true
fi

# Merge playit's settings (same values as "Configuration help -> WaterdogPE")
echo "Applying playit NetherNet configuration..."
python3 - <<'PY'

import os
import yaml


def deep_merge(base, overlay):
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


token = os.environ["NETHERNET_TOKEN"].strip()
if not token:
    raise SystemExit("ERROR: NETHERNET_TOKEN is empty")

backend = os.environ["BACKEND_ADDRESS"]

overlay = {
    "listener": {
        "motd": os.environ.get(
            "WATERDOG_MOTD", "Bedrock via Waterdog and playit"
        ),
        "name": os.environ.get("WATERDOG_SERVER_NAME", "bds-test"),
        "priorities": ["vanilla"],
        "host": "0.0.0.0:19132",
        "transport": "nethernet",
        "max_players": 10,
    },
    "servers": {
        "vanilla": {
            "address": backend,
            "public_address": backend,
            "server_type": "nethernet",
        }
    },
    "nethernet": {
        "signaling": {
            "mode": "nxs",
            "advertise_addresses": [],
            "stun_discovery": False,
            "trusted_proxies": [],
            "nxs": {
                "token": token,
                "endpoint": "https://nethernet.playit.gg",
                "advanced": {
                    "assisted_joins": False,
                    "connection_checks": True,
                    "location": {},
                },
            },
        },
    },
    "online_mode": True,
    "upstream_encryption": True,
    "use_login_extras": (
        os.environ.get("WATERDOG_LOGIN_EXTRAS", "false").lower() == "true"
    ),
    "enable_edu_features": False,
}

with open("config.yml") as f:
    config = yaml.safe_load(f) or {}

deep_merge(config, overlay)

with open("config.yml", "w") as f:
    yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)

print("WaterdogPE configured for Playit NXS signaling.")
print("NXS token: configured")
print("STUN discovery: disabled")
PY

# Wait for the backend (shares this network namespace) before starting
HOSTPORT="${BACKEND_ADDRESS}"
echo "Waiting for BDS at http://${HOSTPORT}/v1/join ..."
for i in $(seq 1 120); do
    if curl -fs "http://${HOSTPORT}/v1/join" >/dev/null 2>&1; then
        echo "BDS is up."
        break
    fi
    [ "$i" -eq 120 ] && echo "WARNING: BDS did not answer after 120s; starting Waterdog anyway."
    sleep 1
done

echo "Starting WaterdogPE..."
exec java -Xms256M -Xmx1G -jar Waterdog.jar