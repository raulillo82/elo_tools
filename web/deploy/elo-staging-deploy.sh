#!/bin/bash
# Deploys staging from the server itself: the branch "staging" if it exists,
# and main if it doesn't.
#
# Staging runs code that hasn't been merged, so unlike production this script
# never installs anything from the repository outside the image: a branch can't
# change the units of the server. It's installed outside the repository too: to
# update it, copy it by hand to ~/.local/bin.
#
# The data are copies of production's. A second container on the same folder
# would take its SELinux label with :Z, and production would lose access to it.
set -uo pipefail

REPO=${REPO:-$HOME/elo-web-staging/repo}
DATA=${DATA:-$HOME/elo-web-staging/data}
PRODUCTION_DATA=${PRODUCTION_DATA:-$HOME/elo-web/data}
STATE=${STATE:-$HOME/.local/state/elo-staging-deploy}
IMAGE=${IMAGE:-localhost/elo-web-staging}
SERVICE=${SERVICE:-elo-staging.service}
HEALTH_URL=${HEALTH_URL:-http://127.0.0.1:5004/login}
HEALTH_TRIES=${HEALTH_TRIES:-15}
HEALTH_WAIT=${HEALTH_WAIT:-2}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}

log() { echo "[elo-staging-deploy] $1"; }

healthy() {
    local try code
    for ((try = 0; try < HEALTH_TRIES; try++)); do
        code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H 'X-Forwarded-Proto: https' "$HEALTH_URL")
        [ "$code" = 200 ] && return 0
        sleep "$HEALTH_WAIT"
    done
    return 1
}

# Never accounts.db: staging has its own, without passwords
copy_data() {
    local file name changed=1
    for file in "$PRODUCTION_DATA"/players-*.sqlite "$PRODUCTION_DATA"/list_info.json \
                "$PRODUCTION_DATA"/rosters*.json; do
        [ -f "$file" ] || continue
        name=$(basename "$file")
        cmp -s "$file" "$DATA/$name" && continue
        cp "$file" "$DATA/$name.new" && mv "$DATA/$name.new" "$DATA/$name" && changed=0
    done
    return "$changed"
}

restart_new_version() {
    podman image exists "$IMAGE:latest" && { podman tag "$IMAGE:latest" "$IMAGE:previous" || return 1; }
    podman build -q -f "$REPO/web/Containerfile" -t "$IMAGE:latest" "$REPO" || return 1
    systemctl --user restart "$SERVICE" && healthy
}

roll_back() {
    podman image exists "$IMAGE:previous" || return 0
    podman tag "$IMAGE:previous" "$IMAGE:latest" && systemctl --user restart "$SERVICE"
}

mkdir -p "$STATE" "$DATA"
data_changed=no
copy_data && data_changed=yes

branch=staging
git -C "$REPO" ls-remote --quiet --exit-code --heads origin staging > /dev/null
case $? in
    0) ;;
    2) branch=main ;;
    *) log "cannot reach the repository"; exit 1 ;;
esac
git -C "$REPO" fetch --quiet --force origin "$branch" || { log "cannot fetch $branch"; exit 1; }
target=$(git -C "$REPO" rev-parse FETCH_HEAD)
deployed=$(cat "$STATE/deployed" 2>/dev/null)

if [ "$deployed" = "$target" ]; then
    # The web reads the lists when it starts
    [ "$data_changed" = yes ] && systemctl --user restart "$SERVICE"
    exit 0
fi

attempts=0
if [ -f "$STATE/failed" ] && [ "$(cut -d' ' -f1 "$STATE/failed")" = "$target" ]; then
    attempts=$(cut -d' ' -f2 "$STATE/failed")
fi
[ "$attempts" -ge "$MAX_ATTEMPTS" ] && exit 0
echo "$target $((attempts + 1))" > "$STATE/failed"
log "deploying $branch at $target, attempt $((attempts + 1)) of $MAX_ATTEMPTS"

git -C "$REPO" checkout --quiet --force --detach "$target" || { log "cannot check it out"; exit 1; }
if ! restart_new_version; then
    log "FAILED: going back to the previous version"
    roll_back
    exit 1
fi

echo "$target" > "$STATE/deployed"
rm -f "$STATE/failed"
podman image prune -f > /dev/null
log "deployed $branch at $target"
