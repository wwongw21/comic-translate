#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Comic Translate"
APP_BUNDLE="dist/${APP_NAME}.app"
OUTPUT_DMG="dist/${APP_NAME}.dmg"
VOLUME_ICON="resources/icons/icon.icns"
STAGING_DIR=""

cleanup() {
    if [[ -n "$STAGING_DIR" && -d "$STAGING_DIR" ]]; then
        rm -rf "$STAGING_DIR"
    fi
}
trap cleanup EXIT

if [[ ! -d "$APP_BUNDLE" ]]; then
    printf 'Expected packaged application at %s\n' "$APP_BUNDLE" >&2
    exit 1
fi

if [[ ! -f "$VOLUME_ICON" ]]; then
    printf 'Expected volume icon at %s\n' "$VOLUME_ICON" >&2
    exit 1
fi

command -v create-dmg >/dev/null 2>&1 || {
    printf 'create-dmg must be installed before building the disk image\n' >&2
    exit 1
}
command -v ditto >/dev/null 2>&1 || {
    printf 'ditto must be available to stage the application bundle\n' >&2
    exit 1
}

mkdir -p dist
STAGING_DIR="$(mktemp -d "dist/.comic-translate-dmg.XXXXXX")"
STAGING_APP="$STAGING_DIR/${APP_NAME}.app"
ditto "$APP_BUNDLE" "$STAGING_APP"

if [[ ! -d "$STAGING_APP/Contents" ]]; then
    printf 'Staged application bundle is missing Contents: %s\n' "$STAGING_APP" >&2
    exit 1
fi

create-dmg \
    --overwrite \
    --volname "$APP_NAME" \
    --volicon "$VOLUME_ICON" \
    --window-size 640 420 \
    --icon-size 100 \
    --icon "${APP_NAME}.app" 160 210 \
    --app-drop-link 480 210 \
    "$OUTPUT_DMG" \
    "$STAGING_DIR"
