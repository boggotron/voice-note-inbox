#!/usr/bin/env bash
#
# Preflight / smoke check for the local n8n deployment (issue #3).
#
# Verifies, against a LIVE running container, the two runtime
# properties that cannot be confirmed by static config inspection
# alone:
#   1. The recordings mount is genuinely read-only from inside the
#      container (a write attempt must fail).
#   2. The n8n port is published to localhost only, not 0.0.0.0 / all
#      interfaces.
#
# Requires: a running Docker daemon, the `voice-inbox-n8n` container
# already started via `docker compose up -d` from deploy/.
#
# Usage:
#   ./deploy/preflight.sh
#
# Exit code 0 = all checks passed. Non-zero = at least one check
# failed; details are printed for each check.

set -uo pipefail

COMPOSE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/docker-compose.yml"
CONTAINER_NAME="voice-inbox-n8n"
FAILURES=0

fail() {
  echo "FAIL: $1"
  FAILURES=$((FAILURES + 1))
}

pass() {
  echo "PASS: $1"
}

echo "== Voice Inbox n8n deployment preflight =="
echo "compose file: $COMPOSE_FILE"
echo

# --- 0. Sanity: daemon reachable, container running ---
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not reachable. Start Docker and re-run this script."
  exit 2
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "ERROR: Container '$CONTAINER_NAME' is not running."
  echo "       Start it first: docker compose --env-file deploy/.env -f \"$COMPOSE_FILE\" up -d"
  exit 2
fi

# --- 1. Recordings mount must be read-only ---
echo "-- Check: recordings mount is read-only --"
if docker exec "$CONTAINER_NAME" sh -c 'test -d /data/recordings'; then
  PROBE_FILE="/data/recordings/.preflight-write-probe-$$"
  if docker exec "$CONTAINER_NAME" sh -c "echo probe > '$PROBE_FILE'" >/dev/null 2>&1; then
    fail "write to /data/recordings inside the container SUCCEEDED — mount is not read-only"
    docker exec "$CONTAINER_NAME" sh -c "rm -f '$PROBE_FILE'" >/dev/null 2>&1
  else
    pass "write to /data/recordings inside the container was rejected (mount is read-only)"
  fi
else
  fail "/data/recordings does not exist inside the container — cannot verify read-only mount"
fi
echo

# --- 2. Output mount must be writable ---
echo "-- Check: output mount is writable --"
PROBE_FILE="/data/output/.preflight-write-probe-$$"
if docker exec "$CONTAINER_NAME" sh -c "echo probe > '$PROBE_FILE' && rm -f '$PROBE_FILE'" >/dev/null 2>&1; then
  pass "write to /data/output inside the container succeeded (mount is read-write, as expected)"
else
  fail "write to /data/output inside the container FAILED — expected read-write mount"
fi
echo

# --- 3. Port must be bound to localhost only ---
echo "-- Check: published port is localhost-only --"
PORT_BINDINGS="$(docker port "$CONTAINER_NAME" 5678 2>/dev/null || true)"
if [ -z "$PORT_BINDINGS" ]; then
  fail "could not read port bindings for $CONTAINER_NAME (is port 5678 published?)"
else
  echo "  reported bindings: $PORT_BINDINGS"
  if echo "$PORT_BINDINGS" | grep -qE '^(0\.0\.0\.0|\[::\]|::)'; then
    fail "port 5678 is bound to all interfaces, not localhost only: $PORT_BINDINGS"
  elif echo "$PORT_BINDINGS" | grep -qE '^127\.0\.0\.1:'; then
    pass "port 5678 is bound to 127.0.0.1 only"
  else
    fail "unrecognized port binding format, please inspect manually: $PORT_BINDINGS"
  fi
fi
echo

# --- 4. Execute Command node must be excluded ---
echo "-- Check: Execute Command node is excluded --"
NODES_EXCLUDE_VALUE="$(docker exec "$CONTAINER_NAME" sh -c 'printenv NODES_EXCLUDE' 2>/dev/null || true)"
if echo "$NODES_EXCLUDE_VALUE" | grep -q 'n8n-nodes-base.executeCommand'; then
  pass "NODES_EXCLUDE includes n8n-nodes-base.executeCommand ($NODES_EXCLUDE_VALUE)"
else
  fail "NODES_EXCLUDE does not include n8n-nodes-base.executeCommand (got: '$NODES_EXCLUDE_VALUE')"
fi
echo

echo "== Summary =="
if [ "$FAILURES" -eq 0 ]; then
  echo "All checks passed."
  exit 0
else
  echo "$FAILURES check(s) failed."
  exit 1
fi
