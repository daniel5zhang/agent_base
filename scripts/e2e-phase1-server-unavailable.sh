#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/output/playwright"
mkdir -p "$OUTPUT_DIR"

PWCLI="${PWCLI:-${CODEX_HOME:-$HOME/.codex}/skills/playwright/scripts/playwright_cli.sh}"
APP_PORT="${APP_PORT:-3011}"
APP_URL="${APP_URL:-http://127.0.0.1:${APP_PORT}}"
UNAVAILABLE_SERVER_URL="${UNAVAILABLE_SERVER_URL:-http://127.0.0.1:8999}"
COMMAND_TIMEOUT_SECONDS="${COMMAND_TIMEOUT_SECONDS:-120}"
NEXT_LOG="$OUTPUT_DIR/phase1-server-unavailable-next.log"
NEXT_PID=""

log() {
  printf '[phase1-unavailable-e2e] %s %s\n' "$(date '+%H:%M:%S')" "$*"
}

run_with_timeout() {
  local seconds="$1"
  shift
  python3 - "$seconds" "$@" <<'PY'
import subprocess
import sys

seconds = int(sys.argv[1])
command = sys.argv[2:]
try:
    raise SystemExit(subprocess.run(command, timeout=seconds).returncode)
except subprocess.TimeoutExpired:
    print(f"Command timed out after {seconds}s: {' '.join(command)}", file=sys.stderr)
    raise SystemExit(124)
PY
}

if [[ ! -x "$PWCLI" ]]; then
  echo "Playwright CLI wrapper not found: $PWCLI" >&2
  exit 1
fi

cleanup() {
  if [[ -n "$NEXT_PID" ]] && kill -0 "$NEXT_PID" >/dev/null 2>&1; then
    kill "$NEXT_PID" >/dev/null 2>&1 || true
    wait "$NEXT_PID" >/dev/null 2>&1 || true
  fi
}

wait_for_app() {
  python3 - "$APP_URL" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
deadline = time.time() + 90
last_error = ""
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception as exc:
        last_error = str(exc)
    time.sleep(1)

print(f"App did not become ready at {url}: {last_error}", file=sys.stderr)
raise SystemExit(1)
PY
}

trap cleanup EXIT

if [[ ! -f "$ROOT_DIR/.next/BUILD_ID" ]]; then
  echo "Production build not found. Run npm run build before server-unavailable E2E." >&2
  exit 1
fi

log "Start isolated Next.js production app: $APP_URL"
(
  cd "$ROOT_DIR"
  WORKBENCH_SERVER_URL="$UNAVAILABLE_SERVER_URL" npm run start -- --hostname 127.0.0.1 --port "$APP_PORT"
) >"$NEXT_LOG" 2>&1 &
NEXT_PID="$!"

wait_for_app

log "Open app: $APP_URL"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" open "$APP_URL" --headed >/dev/null

log "Run server-unavailable browser check"
APP_URL="$APP_URL" run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" run-code --filename "$ROOT_DIR/scripts/e2e-server-unavailable.playwright.js" > "$OUTPUT_DIR/phase1-server-unavailable.snapshot.txt"

grep -q "服务端不可用或运行失败" "$OUTPUT_DIR/phase1-server-unavailable.snapshot.txt"
grep -q "服务端不可用测试，请保留可见错误" "$OUTPUT_DIR/phase1-server-unavailable.snapshot.txt"

log "Server unavailable E2E passed. Evidence saved under $OUTPUT_DIR"
