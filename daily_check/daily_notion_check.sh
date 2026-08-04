#!/bin/bash
# 매일 한 번, 서버에서 그날 새로 생긴 작업이 있는지 확인해서
# 있으면 노션 "전기차 접근성" 페이지에 요약을 이어붙이는 스크립트.
# crontab에서 이 스크립트를 호출.
cd /Users/jeongminwoo/ev-charger-accessibility/daily_check || exit 1

# cron은 macOS 로그인 키체인에 접근하지 못해 OAuth 로그인이 "Not logged in"으로 실패함.
# 키체인 없이 인증하도록 setup-token으로 발급받은 장기 토큰을 사용.
export CLAUDE_CODE_OAUTH_TOKEN="$(cat ~/.claude_cron_token.txt)"

# cron은 TMPDIR/USER/LOGNAME을 비워두거나 다르게 설정해서, Notion MCP(원격) 서버가
# "아직 인증되지 않음" 오류를 내며 실패함. 인터랙티브 세션과 동일하게 명시적으로 지정해 해결.
export TMPDIR="$(getconf DARWIN_USER_TEMP_DIR)"
export USER="$(id -un)"
export LOGNAME="$(id -un)"

PROMPT="$(cat daily_notion_check_prompt.txt)"

echo "=== $(date) 실행 시작 (prompt ${#PROMPT}자) ===" >> daily_notion_check.log

# macOS엔 GNU timeout이 없어서 백그라운드 감시자로 하드 타임아웃(10분) 구현.
# claude가 멈춰도(권한 분류기 hang 등) 무한정 매달려 빈 로그만 남기지 않도록 함.
/Users/jeongminwoo/.local/bin/claude -p "$PROMPT" \
  --allowedTools "Bash" "mcp__notion__notion-update-page" "mcp__notion__notion-search" "mcp__notion__notion-fetch" \
  >> daily_notion_check.log 2>&1 &
CLAUDE_PID=$!

( sleep 600; kill -9 "$CLAUDE_PID" 2>/dev/null ) &
WATCHER_PID=$!

wait "$CLAUDE_PID"
CLAUDE_EXIT=$?
kill "$WATCHER_PID" 2>/dev/null

if [ "$CLAUDE_EXIT" -eq 137 ]; then
  echo "=== $(date) 실행 완료 (10분 타임아웃으로 강제 종료) ===" >> daily_notion_check.log
else
  echo "=== $(date) 실행 완료 (exit code ${CLAUDE_EXIT}) ===" >> daily_notion_check.log
fi
