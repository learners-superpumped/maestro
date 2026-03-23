#!/usr/bin/env bash
# post-edit-lint.sh — PostToolUse(Edit|Write) hook
# 수정된 파일의 확장자를 감지하여 언어별 linter auto-fix 실행
# 모든 경로에서 exit 0 — Claude 작업을 블로킹하지 않음

if ! command -v jq > /dev/null 2>&1; then
    exit 0
fi

input=$(cat)

# 파일 경로 추출
file=$(echo "$input" | jq -r '.tool_input.file_path // empty')
if [ -z "$file" ] || [ ! -f "$file" ]; then
    exit 0
fi

# 편집 성공 여부 확인 — 실패한 편집에는 lint 불필요
success=$(echo "$input" | jq -r 'if .tool_response.success == false then "false" else "true" end')
if [ "$success" = "false" ]; then
    exit 0
fi

# 확장자별 분기
case "$file" in
    *.py)
        if command -v ruff > /dev/null 2>&1; then
            ruff check --fix "$file" 2>&1 || true
            ruff format "$file" 2>&1 || true
        fi
        ;;
    *.ts|*.tsx|*.js|*.jsx)
        if [ -d "node_modules" ] && command -v npx > /dev/null 2>&1; then
            npx eslint --fix "$file" 2>&1 || true
        fi
        ;;
esac

exit 0
