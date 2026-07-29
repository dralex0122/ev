#!/bin/bash
# 매일 한 번, 서버에서 그날 새로 생긴 작업이 있는지 확인해서
# 있으면 노션 "전기차 접근성" 페이지에 요약을 이어붙이는 스크립트.
# crontab에서 이 스크립트를 호출.
cd /Users/jeongminwoo/ev-charger-accessibility || exit 1

# cron은 macOS 로그인 키체인에 접근하지 못해 OAuth 로그인이 "Not logged in"으로 실패함.
# 키체인 없이 인증하도록 setup-token으로 발급받은 장기 토큰을 사용.
export CLAUDE_CODE_OAUTH_TOKEN="$(cat ~/.claude_cron_token.txt)"

# cron은 TMPDIR/USER/LOGNAME을 비워두거나 다르게 설정해서, Notion MCP(원격) 서버가
# "아직 인증되지 않음" 오류를 내며 실패함. 인터랙티브 세션과 동일하게 명시적으로 지정해 해결.
export TMPDIR="$(getconf DARWIN_USER_TEMP_DIR)"
export USER="$(id -un)"
export LOGNAME="$(id -un)"

PROMPT="$(cat daily_notion_check_prompt.txt)"

/Users/jeongminwoo/.local/bin/claude -p "$PROMPT" \
  --allowedTools "Bash" "mcp__notion__notion-update-page" "mcp__notion__notion-search" "mcp__notion__notion-fetch" \
  >> daily_notion_check.log 2>&1

echo "=== $(date) 실행 완료 ===" >> daily_notion_check.log
