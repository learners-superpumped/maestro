# Maestro

[English](../../README.md) | [한국어](README.md)

자율 AI 에이전트를 위한 태스크 오케스트레이션 데몬. 목표 관리, 태스크 계획, Claude CLI 에이전트 디스패치, 결과 추적을 헤드리스로 수행합니다.

## 빠른 시작

```bash
pip install -e .
maestro init
maestro start
```

`maestro status`에 표시되는 URL로 대시보드를 열 수 있습니다.

## 작동 방식

```text
Goal -> Planner -> Tasks -> Dispatcher -> Claude Agents -> Results
```

1. **Goals** — 달성할 목표를 정의 (타겟, 체크 주기 포함)
2. **Planner** — 목표를 평가하고 태스크를 생성
3. **Dispatcher** — 태스크를 에이전트에 할당
4. **Agents** — Claude CLI로 실행, 모든 도구 접근 가능
5. **Results** — 결과를 리뷰, 승인 또는 재시도

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

### CLI로 모니터링

```bash
maestro status        # 데몬 상태 + 대시보드 URL
maestro task list     # 태스크 목록
maestro goal list     # 목표 목록
maestro schedule list # 스케줄 목록
```

### 대시보드로 모니터링

웹 대시보드는 데몬과 함께 자동으로 실행됩니다. `maestro status`에 표시되는 URL로 접근하세요.

- 태스크, 목표, 스케줄, 에셋, 규칙 조회 및 관리
- 에이전트 결과물 승인/거절/수정 요청
- 비용 및 에이전트 활동 실시간 추적

### 에이전트 작업 승인

`approval_level: 2` (기본값) 태스크는 완료 후 사람의 리뷰를 위해 일시정지됩니다. 대시보드 또는 CLI에서 승인:

```bash
maestro task approve <task-id>
maestro task reject <task-id>
maestro task revise <task-id> --note "톤을 좀 더 캐주얼하게 바꿔주세요"
```

## 설정

모든 설정은 `maestro.yaml`에서 관리합니다. 전체 파라미터는 [설정 레퍼런스](maestro-yaml-reference.md)를 참고하세요.

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

[MIT](LICENSE)
