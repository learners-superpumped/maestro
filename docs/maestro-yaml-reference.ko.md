# maestro.yaml 설정 레퍼런스

[English](maestro-yaml-reference.md) | [한국어](maestro-yaml-reference.ko.md)

`maestro.yaml`의 모든 설정 파라미터에 대한 레퍼런스입니다.

---

## `project` (필수)

| 파라미터     | 타입   | 기본값               | 설명                          |
| ------------ | ------ | -------------------- | ----------------------------- |
| `name`       | string | —                    | 프로젝트 이름 식별자 (필수)   |
| `store_path` | string | `./store/maestro.db` | SQLite 데이터베이스 파일 경로 |

## `daemon`

| 파라미터                 | 타입 | 기본값   | 설명                                             |
| ------------------------ | ---- | -------- | ------------------------------------------------ |
| `planner_interval_ms`    | int  | `300000` | 플래너가 목표를 평가하는 주기 (ms)               |
| `dispatcher_interval_ms` | int  | `10000`  | 디스패처가 대기 중인 태스크를 가져오는 주기 (ms) |
| `reconcile_interval_ms`  | int  | `30000`  | 리컨실러가 멈춘 에이전트를 확인하는 주기 (ms)    |
| `scheduler_interval_ms`  | int  | `10000`  | 스케줄러가 cron 스케줄을 확인하는 주기 (ms)      |

## `concurrency`

| 파라미터           | 타입 | 기본값 | 설명                               |
| ------------------ | ---- | ------ | ---------------------------------- |
| `max_total_agents` | int  | `5`    | 전체 목표에 걸친 최대 동시 에이전트 수 |
| `max_per_goal`     | int  | `1`    | 목표당 최대 동시 에이전트 수       |

## `budget`

| 파라미터              | 타입  | 기본값 | 설명                                          |
| --------------------- | ----- | ------ | --------------------------------------------- |
| `daily_limit_usd`     | float | `30.0` | 24시간 롤링 지출 한도 (USD)                   |
| `per_task_limit_usd`  | float | `5.0`  | 태스크당 지출 한도; 초과 시 태스크 중단       |
| `alert_threshold_pct` | int   | `80`   | 일일 지출이 한도의 이 %에 도달하면 알림 발송  |

## `agent`

모든 에이전트의 전역 기본값.

| 파라미터                | 타입   | 기본값                | 설명                                                                                                                 |
| ----------------------- | ------ | --------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `permission_mode`       | string | `"bypass"`            | `"bypass"` = 모든 도구 사용 가능, 프롬프트 없음 (`--dangerously-skip-permissions`). `"restricted"` = `--allowedTools` 화이트리스트. |
| `default_allowed_tools` | list   | `[Read, Write, Bash]` | `permission_mode: restricted`일 때 도구 화이트리스트. bypass 모드에서는 무시됨.                                        |
| `default_max_turns`     | int    | `20`                  | 강제 중지 전 최대 에이전트 턴 수                                                                                     |
| `stall_timeout_ms`      | int    | `300000`              | 출력 없음 타임아웃 — 이 시간 동안 출력이 없으면 멈춘 것으로 판단 (ms)                                                |
| `turn_timeout_ms`       | int    | `3600000`             | 에이전트 턴당 하드 시간 제한 (ms)                                                                                    |
| `max_review_rounds`     | int    | `3`                   | 리뷰 태스크의 최대 반복 횟수                                                                                         |

## `agents`

이름이 지정된 에이전트 정의. 각 키는 에이전트 이름.

| 파라미터          | 타입   | 기본값                | 설명                                                                              |
| ----------------- | ------ | --------------------- | --------------------------------------------------------------------------------- |
| `role`            | string | `""`                  | 에이전트 역할 설명 (시스템 프롬프트에 포함)                                       |
| `instructions`    | string | `""`                  | 프롬프트 파일 경로 (프로젝트 루트 기준 상대 경로)                                 |
| `tools`           | list   | `[Read, Write, Bash]` | 도구 화이트리스트 (`permission_mode: restricted`일 때만 사용)                      |
| `max_turns`       | int    | `50`                  | 이 에이전트의 최대 턴 수                                                          |
| `no_worktree`     | bool   | `false`               | git worktree 대신 프로젝트 루트에서 실행                                          |
| `permission_mode` | string | `""`                  | 전역 permission_mode 오버라이드. 빈 값 = `agent.permission_mode`에서 상속.        |

### Permission Mode 결정 순서

1. `agents.<name>.permission_mode` (비어있지 않은 경우)
2. `agent.permission_mode` (전역)
3. `"bypass"` (하드 기본값)

## `resources`

동시성 제어를 위한 이름이 지정된 리소스 풀.

```yaml
resources:
  chrome-profiles:
    threads:
      max_concurrent: 1
      path: ./chrome-profiles/threads
```

| 파라미터         | 타입   | 기본값 | 설명                                  |
| ---------------- | ------ | ------ | ------------------------------------- |
| `max_concurrent` | int    | `1`    | 이 리소스의 최대 동시 사용자 수       |
| `path`           | string | `""`   | 리소스 프로필의 파일시스템 경로       |

## `assets`

에셋 파이프라인 설정.

| 파라미터              | 타입   | 기본값     | 설명                                                 |
| --------------------- | ------ | ---------- | ---------------------------------------------------- |
| `default_ttl`         | dict   | 아래 참고  | 에셋 타입별 TTL (일 단위, `null` = 만료 없음)        |
| `cleanup_interval_ms` | int    | `86400000` | 정리 작업 실행 주기 (ms)                             |
| `archive_grace_days`  | int    | `30`       | 아카이브된 에셋이 완전 삭제되기까지의 유예 기간 (일) |
| `gemini_api_key`      | string | `""`       | 임베딩용 Gemini API 키 (또는 `$GEMINI_API_KEY`)      |

기본 TTL: `post: null, engage: 30, research: 7, image: null, video: null, audio: null, document: null`

## `integrations`

### `integrations.slack`

| 파라미터      | 타입   | 기본값 | 설명                       |
| ------------- | ------ | ------ | -------------------------- |
| `webhook_url` | string | `null` | Slack 수신 웹훅 URL        |

### `integrations.linear`

| 파라미터       | 타입   | 기본값 | 설명                |
| -------------- | ------ | ------ | ------------------- |
| `api_key`      | string | `null` | Linear API 키       |
| `project_slug` | string | `null` | Linear 프로젝트 슬러그 |

## `logging`

| 파라미터 | 타입   | 기본값                 | 설명                                            |
| -------- | ------ | ---------------------- | ----------------------------------------------- |
| `level`  | string | `"info"`               | 로그 레벨: `debug`, `info`, `warning`, `error`  |
| `file`   | string | `"./logs/maestro.log"` | 로그 파일 경로                                  |

---

## 환경 변수

모든 문자열 값은 `$VAR_NAME` 치환을 지원합니다:

```yaml
budget:
  daily_limit_usd: $MAESTRO_DAILY_BUDGET
integrations:
  slack:
    webhook_url: $SLACK_WEBHOOK_URL
```

정의되지 않은 변수는 그대로 유지됩니다 (리터럴 `$VAR_NAME`).
