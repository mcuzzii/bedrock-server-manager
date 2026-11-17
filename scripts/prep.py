#!/usr/bin/env python3
"""One-shot prep for the Endstone backend. Safe to run on every `docker compose up`.

1. Finds Endstone's server.properties under /data and applies playit's required values.
2. Finds the plugins folder and installs xuidforward (wheel + libxuidforward.so),
   verified against the release's SHA256SUMS.

On the very first run Endstone has not generated its files yet, so there is nothing
to patch; the script says so and exits 0. Start the stack a second time afterwards.
"""
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
import uuid

DATA = Path(os.environ.get("DATA_DIR", "/data"))
TAG = os.environ.get("XUIDFORWARD_TAG", "v1.0.5")
REPO = "ezchr/xuidforward"
API_URL = os.environ.get(
    "XF_API_URL", f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
)
MAX_DEPTH = 4


PROPS = {
    # Network configuration
    "server-ip": "127.0.0.1",
    "server-port": "19142",
    "server-portv6": "19143",
    "server-udp-ports": "19142",
    "transport": "nethernet",
    "enable-lan-visibility": "false",
    "online-mode": "false",

    # Server identity
    "server-name": os.environ.get("SERVER_NAME", "Dedicated Server"),
    "level-name": os.environ.get("LEVEL_NAME", "world"),

    # World configuration
    "gamemode": os.environ.get("GAMEMODE", "survival"),
    "force-gamemode": os.environ.get("FORCE_GAMEMODE", "false"),
    "difficulty": os.environ.get("DIFFICULTY", "normal"),
    "level-seed": os.environ.get("LEVEL_SEED", ""),

    # Player configuration
    "max-players": os.environ.get("MAX_PLAYERS", "20"),
    "default-player-permission-level": os.environ.get(
        "DEFAULT_PLAYER_PERMISSION_LEVEL", "member"
    ),
    "player-idle-timeout": os.environ.get("PLAYER_IDLE_TIMEOUT", "30"),

    # Performance configuration
    "view-distance": os.environ.get("VIEW_DISTANCE", "32"),
    "tick-distance": os.environ.get("TICK_DISTANCE", "4"),
    "max-threads": os.environ.get("MAX_THREADS", "0"),

    # Gameplay configuration
    "allow-cheats": os.environ.get("ALLOW_CHEATS", "false"),
    "allow-list": os.environ.get("ALLOW_LIST", "false"),
    "texturepack-required": os.environ.get(
        "TEXTUREPACK_REQUIRED", "false"
    ),
    "content-log-file-enabled": os.environ.get(
        "CONTENT_LOG_FILE_ENABLED", "false"
    ),
}

def log(msg):
    print(f"[prep] {msg}", flush=True)


def walk(root, max_depth):
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)
        if len(p.parts) - root_depth >= max_depth:
            dirnames[:] = []
        # never descend into worlds or plugin contents
        dirnames[:] = [d for d in dirnames if d not in ("worlds", "db")]
        yield p, dirnames, filenames


def find_properties():
    hits = [p / "server.properties" for p, _, f in walk(DATA, MAX_DEPTH) if "server.properties" in f]
    hits.sort(key=lambda x: len(x.parts))
    return hits[0] if hits else None


def find_plugins_dir(props_path):
    sibling = props_path.parent / "plugins"
    if sibling.is_dir():
        return sibling
    hits = [p / d for p, dirs, _ in walk(DATA, MAX_DEPTH) for d in dirs if d == "plugins"]
    hits.sort(key=lambda x: len(x.parts))
    if hits:
        return hits[0]
    sibling.mkdir(parents=True, exist_ok=True)
    log(f"no plugins folder found; created {sibling}")
    return sibling


def patch_properties(path, wanted):
    lines = path.read_text(encoding="utf-8").splitlines()
    seen, changed = set(), False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0].strip()
        if key in wanted and key not in seen:
            seen.add(key)
            new = f"{key}={wanted[key]}"
            if line != new:
                lines[i] = new
                changed = True
    for key, value in wanted.items():
        if key not in seen:
            lines.append(f"{key}={value}")
            changed = True
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "endstone-test-prep"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()



def install_xuidforward(plugins):
    marker = plugins / "xuidforward" / ".installed-tag"
    so_path = plugins / "xuidforward" / "libxuidforward.so"

    # Do not trust the installation marker alone.
    wheel_exists = any(plugins.glob("endstone_xuidforward-*.whl"))

    if (
        marker.exists()
        and marker.read_text().strip() == TAG
        and so_path.exists()
        and wheel_exists
    ):
        log(f"xuidforward {TAG} already installed (wheel and shim verified)")
        return

    log(f"xuidforward {TAG} incomplete; restoring missing files")

    log(f"fetching xuidforward {TAG} release info")
    release = json.loads(http_get(API_URL))

    # Preserve the complete GitHub asset metadata, including SHA-256 digests.
    assets = {a["name"]: a for a in release.get("assets", [])}

    wheels = sorted(n for n in assets if n.endswith(".whl"))

    required = wheels + ["libxuidforward.so"]

    if not wheels or "libxuidforward.so" not in assets:
        sys.exit(
            f"[prep] ERROR: release {TAG} lacks a .whl or libxuidforward.so: "
            f"{sorted(assets)}"
        )

    downloads = {}

    for name in required:
        asset = assets[name]
        digest = asset.get("digest")

        if not digest or not digest.startswith("sha256:"):
            sys.exit(f"[prep] ERROR: GitHub provides no SHA-256 digest for {name}")

        data = http_get(asset["browser_download_url"])
        actual = sha256(data)
        expected = digest.removeprefix("sha256:").lower()

        if actual != expected:
            sys.exit(
                f"[prep] ERROR: checksum mismatch for {name}; "
                f"expected {expected}, got {actual}"
            )

        downloads[name] = data
        log(f"verified SHA-256: {name}")

    plugins.joinpath("xuidforward").mkdir(parents=True, exist_ok=True)

    wheel = wheels[0]
    (plugins / wheel).write_bytes(downloads[wheel])
    so_path.write_bytes(downloads["libxuidforward.so"])
    so_path.chmod(0o755)

    marker.write_text(TAG + "\n")

    log(f"installed {wheel} -> {plugins}")
    log(f"installed libxuidforward.so -> {so_path}")

    # An existing plugins/xuidforward/profile.json is never touched.

def patch_xuidforward_config(plugins):
    config_path = plugins / "xuidforward" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {
            "enabled": True,
            "dry_run": False,
            "require_local_source": True,
            "auto_allow_local_addresses": True,
            "allowed_sources": ["127.0.0.1", "::1"],
            "namespace_uuid": str(uuid.uuid4()),
            "require_self_signed_id_match": False,
            "require_digit_xuid": True,
            "stage_ttl_seconds": 5,
        }

    config["dry_run"] = False
    config["require_self_signed_id_match"] = False

    config_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )

    log("configured xuidforward config.json")

def main():
    props = find_properties()

    if props is None:
        props = DATA / "server.properties"
        props.parent.mkdir(parents=True, exist_ok=True)
        props.touch()
        log(f"created initial server.properties: {props}")

    log(f"server.properties: {props}")
    log(
        "updated server.properties"
        if patch_properties(props, PROPS)
        else "server.properties already correct"
    )

    plugins = find_plugins_dir(props)
    log(f"plugins folder: {plugins}")

    install_xuidforward(plugins)
    patch_xuidforward_config(plugins)


if __name__ == "__main__":
    main()