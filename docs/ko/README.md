# Maestro

[English](../../README.md) | [한국어](README.md)

자율 AI 에이전트를 위한 태스크 오케스트레이션 데몬. 목표 관리, 태스크 계획, Claude CLI 에이전트 디스패치, 결과 추적을 헤드리스로 수행합니다.

## 빠른 시작

```bash
pip install -e .
maestro init
maestro start
```

## 데몬

`maestro start`는 전체 오케스트레이션 루프를 실행하는 백그라운드 데몬을 시작합니다:

```bash
maestro start         # 데몬 시작 (백그라운드)
maestro stop          # 데몬 중지
maestro status        # PID, 포트, 대시보드 URL 표시
```

데몬은 4개의 루프를 동시에 실행합니다:

- **Planner** — 목표를 평가하고 태스크를 생성
- **Dispatcher** — 대기 중인 태스크를 Claude CLI 에이전트에 할당
- **Scheduler** — cron 기반 반복 태스크를 트리거
- **Reconciler** — 멈춘 에이전트를 감지하고 타임아웃을 처리

모든 에이전트는 기본적으로 `claude` CLI를 `--dangerously-skip-permissions`로 실행하여, 모든 도구(MCP 서버, WebFetch, WebSearch 등)에 접근할 수 있습니다.

## 웹 대시보드

대시보드는 데몬과 함께 자동으로 시작되며, 사용 가능한 랜덤 포트에서 실행됩니다.

```bash
maestro status        # 표시: http://localhost:<port>
```

대시보드에서 할 수 있는 것:

- 태스크, 목표, 스케줄, 에셋, 규칙 조회 및 관리
- 에이전트 결과물 승인 / 거절 / 수정 요청
- 에이전트 로그 실시간 확인
- 비용 및 활동 추적

대시보드는 `web/dist/`에서 제공되는 React SPA이며, 데몬의 HTTP 서버가 서빙합니다.

## 사용법

### 프로젝트 초기화

```bash
maestro init
```

`maestro.yaml`, `.maestro/` 디렉토리, SQLite 데이터베이스, MCP 서버 설정을 생성합니다.

### 목표 정의

```bash
maestro goal add \
  --id weekly-posts \
  --description "주간 블로그 포스트 3개 발행" \
  --cooldown-hours 168
```

### 태스크 수동 생성

```bash
maestro task add \
  --title "소개 포스트 작성" \
  --instruction "신제품 출시에 대한 블로그 포스트를 작성하세요" \
  --priority 2
```

### 반복 태스크 스케줄링

```bash
maestro schedule add \
  --name daily-review \
  --task-type claude \
  --cron "0 9 * * *"
```

### 에이전트 작업 승인

`approval_level: 2` (기본값) 태스크는 완료 후 사람의 리뷰를 위해 일시정지됩니다:

```bash
maestro task approve <task-id>
maestro task reject <task-id>
maestro task revise <task-id> --note "톤을 좀 더 캐주얼하게 바꿔주세요"
```

## 설정

모든 설정은 `maestro.yaml`에서 관리합니다. 전체 파라미터는 [설정 레퍼런스](CONFIGURATION.md)를 참고하세요.

```yaml
agent:
  permission_mode: bypass    # 모든 도구 사용 가능 (기본값)

agents:
  planner:
    role: "목표에서 태스크를 계획"
    max_turns: 30
    no_worktree: true
  default:
    max_turns: 50

budget:
  daily_limit_usd: 30.0
  per_task_limit_usd: 5.0
```

## 요구사항

- Python 3.11+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) 설치 필요

## 라이선스

[MIT](../../LICENSE)
