
#!/usr/bin/env python3

import copy
import json
import os
import re
from pathlib import Path

from ruamel.yaml import YAML


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "compose.yaml"
ENV_FILE = ROOT / ".env"

NAME = os.environ["SERVER_NAME"].strip()
TOKEN = os.environ["NETHERNET_TOKEN"]
TOKEN_PREFIX = re.sub(r"[^A-Z0-9]+", "_", NAME.upper()).strip("_")

# ---------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------

SETTINGS = {
    "SERVER_NAME": NAME,
    "LEVEL_NAME": os.environ.get("LEVEL_NAME", f"{NAME}-world"),
    "GAMEMODE": os.environ.get("GAMEMODE", "survival"),
    "DIFFICULTY": os.environ.get("DIFFICULTY", "normal"),
    "FORCE_GAMEMODE": os.environ.get("FORCE_GAMEMODE", "false"),
    "MAX_PLAYERS": os.environ.get("MAX_PLAYERS", "20"),
    "VIEW_DISTANCE": os.environ.get("VIEW_DISTANCE", "32"),
    "TICK_DISTANCE": os.environ.get("TICK_DISTANCE", "4"),
    "ALLOW_CHEATS": os.environ.get("ALLOW_CHEATS", "false"),
    "ALLOW_LIST": os.environ.get("ALLOW_LIST", "false"),
    "PLAYER_IDLE_TIMEOUT": os.environ.get("PLAYER_IDLE_TIMEOUT", "30"),
    "DEFAULT_PLAYER_PERMISSION_LEVEL": os.environ.get(
        "DEFAULT_PLAYER_PERMISSION_LEVEL", "member"
    ),
    "TEXTUREPACK_REQUIRED": os.environ.get(
        "TEXTUREPACK_REQUIRED", "false"
    ),
    "CONTENT_LOG_FILE_ENABLED": os.environ.get(
        "CONTENT_LOG_FILE_ENABLED", "false"
    ),
    "MAX_THREADS": os.environ.get("MAX_THREADS", "0"),
    "LEVEL_SEED": os.environ.get("LEVEL_SEED", ""),
}


# ---------------------------------------------------------------------
# Service templates
# ---------------------------------------------------------------------

TEMPLATES = {
    "prep": {
        "image": "python:3.12-slim",
        "container_name": "__NAME__-prep",
        "user": "1000:1000",
        "environment": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "XUIDFORWARD_TAG": "v1.0.5",
        },
        "command": ["python", "/prep.py"],
        "volumes": [
            "./endstone/data/__NAME__:/data",
            "./scripts/prep.py:/prep.py:ro",
        ],
        "restart": "no",
    },

    "endstone": {
        "build": {
            "context": "./endstone",
        },
        "image": "endstone-xuidforward:local",
        "platform": "linux/amd64",
        "container_name": "__NAME__",
        "environment": {
            "PUID": "1000",
            "PGID": "1000",
            "TZ": "Asia/Manila",
        },
        "volumes": [
            "./endstone/data/__NAME__:/data",
        ],
        "networks": ["minecraft"],
        "stdin_open": True,
        "tty": True,
        "stop_grace_period": "15s",
        "restart": "unless-stopped",
        "depends_on": {
            "__NAME__-prep": {
                "condition": "service_completed_successfully"
            }
        },
    },

    "waterdog": {
        "image": "eclipse-temurin:21-jre",
        "container_name": "__NAME__-waterdog",
        "network_mode": "service:__NAME__",
        "working_dir": "/waterdog/__NAME__",
        "entrypoint": ["/bin/sh", "/scripts/waterdog-start.sh"],
        "environment": {
            "NETHERNET_TOKEN": "${__TOKEN_ENV__:-}",
            "BACKEND_ADDRESS": "127.0.0.1:19142",
            "WATERDOG_SERVER_NAME": "__NAME__",
            "WATERDOG_MOTD": "__NAME__ via playit",
            "WATERDOG_LOGIN_EXTRAS": False,
        },
        "volumes": [
            "./waterdog/__NAME__:/waterdog",
            "./scripts/waterdog-start.sh:/scripts/waterdog-start.sh:ro",
        ],
        "depends_on": ["__NAME__"],
        "stdin_open": True,
        "tty": True,
        "restart": "unless-stopped",
    },
}


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

def validate():
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", NAME):
        raise ValueError(
            "Server name must contain only lowercase letters, "
            "numbers, and hyphens."
        )

    if not TOKEN or not TOKEN.strip():
        raise ValueError("A NetherNet token is required.")

    if "\n" in TOKEN or "\r" in TOKEN:
        raise ValueError("The NetherNet token cannot contain newlines.")

    if not re.fullmatch(r"[A-Za-z0-9 _.-]+", SETTINGS["LEVEL_NAME"]):
        raise ValueError(
            "LEVEL_NAME may only contain letters, numbers, spaces, "
            "periods, underscores, and hyphens."
        )

    if SETTINGS["GAMEMODE"] not in {
        "survival", "creative", "adventure"
    }:
        raise ValueError("Invalid GAMEMODE.")

    if SETTINGS["DIFFICULTY"] not in {
        "peaceful", "easy", "normal", "hard"
    }:
        raise ValueError("Invalid DIFFICULTY.")

    if SETTINGS["DEFAULT_PLAYER_PERMISSION_LEVEL"] not in {
        "visitor", "member", "operator"
    }:
        raise ValueError("Invalid default player permission level.")

    boolean_settings = (
        "FORCE_GAMEMODE",
        "ALLOW_CHEATS",
        "ALLOW_LIST",
        "TEXTUREPACK_REQUIRED",
        "CONTENT_LOG_FILE_ENABLED",
    )

    for key in boolean_settings:
        SETTINGS[key] = SETTINGS[key].lower()

        if SETTINGS[key] not in {"true", "false"}:
            raise ValueError(f"{key} must be true or false.")

    integer_settings = {
        "MAX_PLAYERS": 1,
        "VIEW_DISTANCE": 5,
        "TICK_DISTANCE": 4,
        "PLAYER_IDLE_TIMEOUT": 0,
        "MAX_THREADS": 0,
    }

    for key, minimum in integer_settings.items():
        try:
            value = int(SETTINGS[key])
        except ValueError:
            raise ValueError(f"{key} must be an integer.")

        if value < minimum:
            raise ValueError(f"{key} must be at least {minimum}.")

        SETTINGS[key] = str(value)

    if int(SETTINGS["TICK_DISTANCE"]) > 12:
        raise ValueError("TICK_DISTANCE cannot exceed 12.")


# ---------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------

def replace_placeholders(value):
    """Replace template placeholders recursively."""

    if isinstance(value, dict):
        return {
            replace_placeholders(key): replace_placeholders(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [replace_placeholders(item) for item in value]

    if isinstance(value, str):
        return (
            value
            .replace("__NAME__", NAME)
            .replace("__TOKEN_ENV__", f"{TOKEN_PREFIX}_TOKEN")
        )

    return value


def generate_services():
    services = {
        f"{NAME}-prep": copy.deepcopy(TEMPLATES["prep"]),
        NAME: copy.deepcopy(TEMPLATES["endstone"]),
        f"{NAME}-waterdog": copy.deepcopy(TEMPLATES["waterdog"]),
    }

    services = replace_placeholders(services)

    # Supply all server settings to prep.py.
    services[f"{NAME}-prep"]["environment"].update(SETTINGS)

    return services


# ---------------------------------------------------------------------
# .env management
# ---------------------------------------------------------------------

def update_env_file(key, value):
    """Insert or update one variable in the root .env file."""

    lines = (
        ENV_FILE.read_text(encoding="utf-8").splitlines()
        if ENV_FILE.exists()
        else []
    )

    # Single-quoted dotenv values preserve literal characters such as
    # dollar signs, spaces, and # characters.
    escaped_value = value.replace("\\", "\\\\").replace("'", "\\'")
    new_line = f"{key}='{escaped_value}'"

    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")

    matching_lines = [
        index for index, line in enumerate(lines)
        if pattern.match(line)
    ]

    if matching_lines:
        lines[matching_lines[0]] = new_line

        # Remove duplicate definitions of this variable.
        for index in reversed(matching_lines[1:]):
            lines.pop(index)
    else:
        lines.append(new_line)

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# Compose generation
# ---------------------------------------------------------------------

def main():
    validate()

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120

    if COMPOSE_FILE.exists():
        with COMPOSE_FILE.open(encoding="utf-8") as file:
            compose = yaml.load(file) or {}
    else:
        compose = {}

    services = compose.setdefault("services", {})

    if not isinstance(services, dict):
        raise ValueError("compose.yaml must contain a services mapping.")

    new_services = {
        f"{NAME}-prep",
        NAME,
        f"{NAME}-waterdog",
    }

    conflicts = new_services.intersection(services.keys())

    if conflicts:
        raise ValueError(
            "The following Compose services already exist: "
            + ", ".join(sorted(conflicts))
        )

    data_dir = ROOT / "endstone" / "data" / NAME
    waterdog_dir = ROOT / "waterdog" / NAME

    for directory in (data_dir, waterdog_dir):
        if directory.exists() and any(directory.iterdir()):
            raise ValueError(
                f"Directory already exists and is not empty: {directory}"
            )

    # Create per-server directories.
    data_dir.mkdir(parents=True, exist_ok=True)
    waterdog_dir.mkdir(parents=True, exist_ok=True)

    # Generate and append the services.
    services.update(generate_services())

    # Store the token outside compose.yaml.
    update_env_file(f"{TOKEN_PREFIX}_TOKEN", TOKEN)

    with COMPOSE_FILE.open("w", encoding="utf-8") as file:
        yaml.dump(compose, file)

    print(f"Provisioned Compose definitions for '{NAME}'.")
    print(f"Data directory:    {data_dir}")
    print(f"Waterdog directory: {waterdog_dir}")
    print(f"Token variable:    {TOKEN_PREFIX}_TOKEN")


if __name__ == "__main__":
    main()
