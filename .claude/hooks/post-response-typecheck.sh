#!/usr/bin/env bash
# post-response-typecheck.sh — Stop hook
# 변경된 파일을 git으로 수집하여 언어별 타입 체크 실행
# 모든 경로에서 exit 0 — Claude 작업을 블로킹하지 않음

# stdin 소비 (Stop 이벤트 payload — 파일 정보 미포함)
cat > /dev/null

# 변경된 파일 수집 (staged + unstaged + untracked)
py_files=$(
    { git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
    | sort -u | grep '\.py$' || true
)

ts_files=$(
    { git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
    | sort -u | grep -E '\.(ts|tsx)$' || true
)

# Python 타입 체크
if [ -n "$py_files" ] && command -v mypy > /dev/null 2>&1; then
    echo "[typecheck] Running mypy on changed Python files..." >&2
    echo "$py_files" | xargs mypy --no-error-summary 2>&1 >&2 || true
fi

# TypeScript 타입 체크
if [ -n "$ts_files" ] && command -v npx > /dev/null 2>&1 && [ -f "tsconfig.json" ]; then
    echo "[typecheck] Running tsc on changed TypeScript files..." >&2
    npx tsc --noEmit 2>&1 >&2 || true
fi

exit 0
