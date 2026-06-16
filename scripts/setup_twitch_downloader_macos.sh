#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="$ROOT_DIR/tools/twitchdownloader"
API_URL="https://api.github.com/repos/lay295/TwitchDownloader/releases/latest"

mkdir -p "$INSTALL_DIR"

ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  ASSET_HINT="MacOSArm64"
else
  ASSET_HINT="MacOS"
fi

ASSET_URL="$(
  ASSET_HINT="$ASSET_HINT" python3 - <<'PY'
import json
import os
import sys
import urllib.request

api_url = "https://api.github.com/repos/lay295/TwitchDownloader/releases/latest"
hint = os.environ["ASSET_HINT"]
with urllib.request.urlopen(api_url, timeout=30) as response:
    release = json.load(response)

assets = release.get("assets", [])
matches = [
    asset
    for asset in assets
    if "TwitchDownloaderCLI" in asset.get("name", "")
    and hint in asset.get("name", "")
    and asset.get("name", "").endswith(".zip")
]

if hint == "MacOS" and matches:
    matches = [asset for asset in matches if "Arm64" not in asset.get("name", "")] or matches

if not matches:
    print("Could not find a matching macOS TwitchDownloaderCLI release asset.", file=sys.stderr)
    print("Download it manually from https://github.com/lay295/TwitchDownloader/releases", file=sys.stderr)
    sys.exit(1)

print(matches[0]["browser_download_url"])
PY
)"

ZIP_PATH="$INSTALL_DIR/TwitchDownloaderCLI.zip"
echo "Downloading $ASSET_URL"
curl -L "$ASSET_URL" -o "$ZIP_PATH"

rm -f "$INSTALL_DIR/TwitchDownloaderCLI"
unzip -o "$ZIP_PATH" -d "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/TwitchDownloaderCLI"

if command -v xattr >/dev/null 2>&1; then
  xattr -d com.apple.quarantine "$INSTALL_DIR/TwitchDownloaderCLI" 2>/dev/null || true
fi

echo "Installed: $INSTALL_DIR/TwitchDownloaderCLI"
echo "Next: python -m twitch_promo_analyzer download-vod 'https://www.twitch.tv/videos/2776778244?sr=a'"
