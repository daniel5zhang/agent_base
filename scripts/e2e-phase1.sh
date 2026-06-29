#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/output/playwright"
mkdir -p "$OUTPUT_DIR"

PWCLI="${PWCLI:-${CODEX_HOME:-$HOME/.codex}/skills/playwright/scripts/playwright_cli.sh}"
APP_URL="${APP_URL:-http://127.0.0.1:3001}"
SERVER_URL="${WORKBENCH_SERVER_URL:-http://127.0.0.1:8000}"
COMMAND_TIMEOUT_SECONDS="${COMMAND_TIMEOUT_SECONDS:-120}"

log() {
  printf '[phase1-e2e] %s %s\n' "$(date '+%H:%M:%S')" "$*"
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

assert_contains() {
  local file="$1"
  local expected="$2"
  if ! grep -q "$expected" "$file"; then
    echo "Expected text not found in $file: $expected" >&2
    echo "---- $file tail ----" >&2
    tail -n 80 "$file" >&2 || true
    exit 1
  fi
}

assert_not_contains() {
  local file="$1"
  local unexpected="$2"
  if grep -q "$unexpected" "$file"; then
    echo "Unexpected text found in $file: $unexpected" >&2
    echo "---- $file matching lines ----" >&2
    grep -n "$unexpected" "$file" >&2 || true
    exit 1
  fi
}

capture_snapshot() {
  local snapshot_name="$1"
  local output_file="$OUTPUT_DIR/$snapshot_name.snapshot.txt"
  log "Capture snapshot: $snapshot_name"
  run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" snapshot > "$output_file"
}

capture_snapshot_until() {
  local snapshot_name="$1"
  local max_seconds="$2"
  shift 2
  local output_file="$OUTPUT_DIR/$snapshot_name.snapshot.txt"
  local started="$SECONDS"
  local missing=()

  while true; do
    capture_snapshot "$snapshot_name"
    missing=()
    for expected in "$@"; do
      if ! grep -q "$expected" "$output_file"; then
        missing+=("$expected")
      fi
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
      return 0
    fi
    if (( SECONDS - started >= max_seconds )); then
      echo "Timed out waiting for expected text in $output_file: ${missing[*]}" >&2
      echo "---- $output_file tail ----" >&2
      tail -n 100 "$output_file" >&2 || true
      exit 1
    fi
    log "Waiting for $snapshot_name: ${missing[*]}"
    sleep 3
  done
}

if [[ ! -x "$PWCLI" ]]; then
  echo "Playwright CLI wrapper not found: $PWCLI" >&2
  exit 1
fi

log "Check server health: $SERVER_URL"
run_with_timeout 10 curl -fsS "$SERVER_URL/health" >/dev/null
run_with_timeout 10 curl -fsS "$SERVER_URL/api/diagnostics" | grep -q '"sqlite":"ok"'

log "Reset Playwright browser session"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" close-all >/dev/null 2>&1 || true
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" kill-all >/dev/null 2>&1 || true
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" close >/dev/null 2>&1 || true

log "Open app: $APP_URL"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" open "$APP_URL" --headed >/dev/null
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" delete-data >/dev/null 2>&1 || true
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" open "$APP_URL" --headed >/dev/null
capture_snapshot "phase1-initial"
assert_contains "$OUTPUT_DIR/phase1-initial.snapshot.txt" 'textbox "发送消息"'
assert_contains "$OUTPUT_DIR/phase1-initial.snapshot.txt" "最近会话"

log "Open settings"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" click e49 >/dev/null
capture_snapshot "phase1-settings"
assert_contains "$OUTPUT_DIR/phase1-settings.snapshot.txt" "模型与设置"
assert_contains "$OUTPUT_DIR/phase1-settings.snapshot.txt" "qwen3.7-plus"
assert_contains "$OUTPUT_DIR/phase1-settings.snapshot.txt" "模型已配置"

log "Reopen app after settings check"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" open "$APP_URL" --headed >/dev/null
capture_snapshot "phase1-initial-after-settings"
assert_contains "$OUTPUT_DIR/phase1-initial-after-settings.snapshot.txt" 'textbox "发送消息"'

send_and_assert() {
  local message="$1"
  local snapshot_name="$2"
  local wait_seconds="$3"
  shift 3

  log "Send: $snapshot_name"
  run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" fill e65 "$message" >/dev/null
  run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" press Enter >/dev/null
  sleep "$wait_seconds"
  capture_snapshot_until "$snapshot_name" 90 "$@"
}

send_and_assert \
  "用一句话说明你是企业 Agent 工作台" \
  "phase1-general-chat" \
  8 \
  "执行过程" \
  "复制" \
  "重新生成"

send_and_assert \
  "帮我总结刚才讨论" \
  "phase1-summarize" \
  8 \
  "执行过程" \
  "复制" \
  "重新生成"

send_and_assert \
  "改写这段说明，让它更简洁：一阶段要先跑通通用 Agent 能力" \
  "phase1-rewrite" \
  8 \
  "执行过程" \
  "复制" \
  "重新生成"

send_and_assert \
  "帮我制定一阶段验收计划" \
  "phase1-plan" \
  2 \
  "一阶段验收计划" \
  "plan.update" \
  "审计编号"

send_and_assert \
  "读取 mvp-stage-plan.md 文件" \
  "phase1-workspace-read" \
  2 \
  "文件预览：mvp-stage-plan.md" \
  "workspace.read" \
  "已生成文件预览"

send_and_assert \
  "记住：我偏好简洁输出" \
  "phase1-memory-write" \
  2 \
  "已写入受控记忆" \
  "memory.write"

send_and_assert \
  "读取我的记忆偏好" \
  "phase1-memory-read" \
  2 \
  "受控记忆快照" \
  "memory.read" \
  "已读取受控记忆"

send_and_assert \
  "查看当前模型和工作空间设置" \
  "phase1-settings-tool" \
  2 \
  "设置快照" \
  "settings.read" \
  "已生成设置快照"

send_and_assert \
  "本地分析 10 20 30 的平均值" \
  "phase1-local-analysis" \
  2 \
  "本地数据分析" \
  "local_data.analyze" \
  "已生成本地数据分析"

send_and_assert \
  "更新一阶段计划产物，加入取消和重试检查" \
  "phase1-artifact-update" \
  2 \
  "更新后的一阶段计划" \
  "artifact.update" \
  "已更新 Artifact"

send_and_assert \
  "运行诊断检查服务端模型和工具状态" \
  "phase1-diagnostic-tool" \
  2 \
  "诊断报告" \
  "diagnostic.check" \
  "已生成诊断报告"

send_and_assert \
  "查 2026 年所有惠民保项目总保费" \
  "phase1-business-block" \
  2 \
  "业务插件将在二阶段启用" \
  "请求已被一阶段边界阻断"

send_and_assert \
  "触发失败工具测试" \
  "phase1-tool-failure" \
  2 \
  "工具执行失败" \
  "diagnostic.check" \
  "取消运行" \
  "重试运行"

log "Open events tab"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" click e86 >/dev/null
capture_snapshot_until "phase1-events" 90 "run.failed" "tool:diagnostic.check"
for snapshot_file in "$OUTPUT_DIR"/phase1-*.snapshot.txt; do
  assert_not_contains "$snapshot_file" "IndexError"
done

log "Capture final screenshot"
run_with_timeout "$COMMAND_TIMEOUT_SECONDS" "$PWCLI" screenshot > "$OUTPUT_DIR/phase1-final-screenshot.log"

log "Phase 1 E2E passed. Evidence saved under $OUTPUT_DIR"
