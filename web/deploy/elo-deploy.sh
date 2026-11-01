#!/bin/bash
# Deploys the web from the server itself, following origin/main.
#
# Runs from a systemd timer, so nothing outside this machine can make it run
# anything: it only reads the public repository. main only gets code through
# pull requests with their tests passed.
#
# If the new version doesn't answer, it goes back to the previous image. A
# commit that fails is retried MAX_ATTEMPTS times and then left alone until a
# newer one arrives. It's installed outside the repository, so a commit can't
# change this script: to update it, copy it by hand to ~/.local/bin.
set -uo pipefail

REPO=${REPO:-$HOME/elo-web/repo}
STATE=${STATE:-$HOME/.local/state/elo-deploy}
UNITS=${UNITS:-$HOME/.config/systemd/user}
IMAGE=${IMAGE:-localhost/elo-web}
HEALTH_URL=${HEALTH_URL:-http://127.0.0.1:5003/login}
HEALTH_TRIES=${HEALTH_TRIES:-15}
HEALTH_WAIT=${HEALTH_WAIT:-2}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}

log() { echo "[elo-deploy] $1"; }

healthy() {
    local try code
    for ((try = 0; try < HEALTH_TRIES; try++)); do
        code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H 'X-Forwarded-Proto: https' "$HEALTH_URL")
        [ "$code" = 200 ] && return 0
        sleep "$HEALTH_WAIT"
    done
    return 1
}

# The tags are only moved once the new image has been built
restart_new_version() {
    podman tag "$IMAGE:latest" "$IMAGE:previous" || return 1
    podman build -q -f "$REPO/web/Containerfile" -t "$IMAGE:latest" "$REPO" || return 1
    systemctl --user restart elo-web.service && healthy
}

roll_back() {
    podman tag "$IMAGE:previous" "$IMAGE:latest" && systemctl --user restart elo-web.service
}

mkdir -p "$STATE"
git -C "$REPO" fetch --quiet origin main || { log "cannot fetch origin/main"; exit 1; }
target=$(git -C "$REPO" rev-parse FETCH_HEAD)
[ -f "$STATE/deployed" ] || git -C "$REPO" rev-parse HEAD > "$STATE/deployed"
deployed=$(cat "$STATE/deployed")
[ "$deployed" = "$target" ] && exit 0

attempts=0
if [ -f "$STATE/failed" ] && [ "$(cut -d' ' -f1 "$STATE/failed")" = "$target" ]; then
    attempts=$(cut -d' ' -f2 "$STATE/failed")
fi
[ "$attempts" -ge "$MAX_ATTEMPTS" ] && exit 0
echo "$target $((attempts + 1))" > "$STATE/failed"
log "deploying $target, attempt $((attempts + 1)) of $MAX_ATTEMPTS"

git -C "$REPO" merge --quiet --ff-only "$target" || { log "cannot fast-forward"; exit 1; }

# Only what goes in the image needs a rebuild
if ! git -C "$REPO" diff --quiet "$deployed" "$target" -- web elo_names.py; then
    install -m 644 "$REPO"/web/deploy/*.service "$REPO"/web/deploy/*.timer "$UNITS"/
    systemctl --user daemon-reload
    if ! restart_new_version; then
        log "FAILED: going back to the previous version"
        roll_back
        exit 1
    fi
fi

echo "$target" > "$STATE/deployed"
rm -f "$STATE/failed"
# Each build leaves the image before the previous one without a tag
podman image prune -f > /dev/null
log "deployed $target"
