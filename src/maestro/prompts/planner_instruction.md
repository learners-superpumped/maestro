다음 목표와 신호를 분석하여 실행 태스크를 생성하라.

## Goals
{goals}

{history_section}## Signals
{signals}

중요: 각 태스크에 agent 필드를 지정하라. agent는 태스크를 실행할 에이전트 유형이다.

## 태스크 순서 지정
각 태스크에 depends_on_steps 필드로 선행 태스크의 배열 인덱스(0부터)를 지정하라.
선행 태스크의 결과가 필요한 경우에만 의존성을 추가하라.
병렬 실행 가능한 태스크는 depends_on_steps를 비워두라.

예시:
[{{"title": "리서치", "agent": "default"}},
 {{"title": "감사", "agent": "default"}},
 {{"title": "최적화", "agent": "default", "depends_on_steps": [0, 1]}}]

JSON 배열로 반환하라.
