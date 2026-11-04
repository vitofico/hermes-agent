#!/bin/sh
# Disposable native-runtime acceptance: no external network or real credentials.
set -eu
image=${1:?Usage: tests/smoke-image.sh IMAGE}
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
container=$(docker create --platform linux/amd64 --network none \
    --cap-drop ALL --security-opt no-new-privileges \
    -e ANTHROPIC_API_KEY=synthetic-not-a-key \
    -e WEBHOOK_ENABLED=true -e WEBHOOK_SECRET=synthetic-webhook-secret \
    "$image")
cleanup() { docker rm -fv "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
# The image owns its home as UID10000; copied config remains readable, not writable.
docker cp "$root/examples/config.yaml" "$container:/opt/data/.hermes/config.yaml" >/dev/null
docker start "$container" >/dev/null
wait_ready() {
    ready=false
    attempt=0
    while [ "$attempt" -lt 30 ]; do
        if docker exec "$container" /opt/hermes/.venv/bin/python -c \
            'import json,urllib.request; assert json.load(urllib.request.urlopen("http://127.0.0.1:8644/health",timeout=2))["status"] == "ok"' >/dev/null 2>&1; then
            ready=true
            break
        fi
        if [ "$(docker inspect --format '{{.State.Running}}' "$container")" != true ]; then break; fi
        attempt=$((attempt + 1))
        sleep 2
    done
    if [ "$ready" != true ]; then
        docker logs "$container" >&2
        echo 'Gateway never became healthy' >&2
        exit 1
    fi
}
wait_ready
# Reuse the same writable home after an ungraceful stop: stale gateway PID/lock
# files must not prevent a new gateway process from becoming healthy.
docker kill --signal KILL "$container" >/dev/null
docker start "$container" >/dev/null
wait_ready
docker exec -i "$container" /opt/hermes/.venv/bin/python - <<'PY'
import os
from model_tools import get_tool_definitions
assert os.getuid() == 10000
assert os.environ['HERMES_HOME'] == '/opt/data/.hermes'
assert get_tool_definitions(enabled_toolsets=[], quiet_mode=True) == []
PY
docker stop --time 10 "$container" >/dev/null
status=$(docker inspect --format '{{.State.ExitCode}}' "$container")
# Pinned gateway/run_shutdown.py deliberately returns 1 for unplanned SIGTERM,
# after graceful teardown, so service managers can revive the process. Require
# its native signal-handler evidence and exact verdict; never accept SIGKILL137.
if [ "$status" != 1 ] || ! docker logs "$container" 2>&1 | grep -F 'Shutdown context: signal=SIGTERM' >/dev/null; then
    docker logs "$container" >&2
    echo "Unexpected gateway shutdown: $status" >&2
    exit 1
fi
printf '%s\n' 'Gateway image smoke passed: non-root, isolated health, empty tools, forced-stop recovery, graceful shutdown'
