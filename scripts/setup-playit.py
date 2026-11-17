
#!/usr/bin/env python3

import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
KEY = "PLAYIT_SECRET_KEY"


def update_env_file(value: str):
    """Add or update PLAYIT_SECRET_KEY in the root .env file."""

    lines = (
        ENV_FILE.read_text(encoding="utf-8").splitlines()
        if ENV_FILE.exists()
        else []
    )

    escaped_value = value.replace("\\", "\\\\").replace("'", "\\'")
    new_line = f"{KEY}='{escaped_value}'"

    pattern = re.compile(rf"^\s*{re.escape(KEY)}\s*=")

    matches = [
        index for index, line in enumerate(lines)
        if pattern.match(line)
    ]

    if matches:
        lines[matches[0]] = new_line

        for index in reversed(matches[1:]):
            lines.pop(index)
    else:
        lines.append(new_line)

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main():
    token = os.environ.get("TOKEN", "")

    if not token.strip():
        raise ValueError("A Playit secret key is required.")

    if "\n" in token or "\r" in token:
        raise ValueError("The Playit secret key cannot contain newlines.")

    update_env_file(token)

    print("Updated PLAYIT_SECRET_KEY in .env.")


if __name__ == "__main__":
    main()
