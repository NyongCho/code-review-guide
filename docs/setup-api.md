# GitHub-hosted API 방식

ChatGPT 구독과 API 과금은 별도다. API 프로젝트·모델 접근·검증 예산을 확인한 후 실행한다. key 값은 채팅이나 repo에 넣지 않는다.

1. 프로젝트 설정의 mode를 `api`로 명시하고 `api_budget.approved_usd`, `api_budget.max_calls`를 지정한다. 이는 승인된 예산과 호출 제한이며, 공급자 측 강제 비용 상한의 존재를 보장하지 않는다.
2. 보호된 default branch만 접근 가능한 GitHub Environment `review-runtime`을 만든다. 키는 그 환경의 `OPENAI_API_KEY` secret으로 등록한다. feature/PR ref에서 접근이 거절되는지 합성 canary로 확인한다.
3. 공식 `openai/codex-action`을 `13e9c17417b29e9a276f73ec6ed7fb574137d3c3`로 고정하고 CLI 버전·모델·추론 강도도 기록한다. `openai-api-key` 입력만 키를 받으며 저장소 코드 job의 공통 환경에 두지 않는다.
4. 일회성 Linux runner에서 `safety-strategy: drop-sudo`와 읽기 제한 permission profile을 사용한다. `sandbox`와 함께 지정하지 않는다. [격리 검사](decisions/runtime-isolation.md)를 통과하기 전 실제 PR 입력으로 모델을 호출하지 않는다.
5. 생성 결과, 자격증명 없는 테스트, GitHub 게시를 분리한다. Action 실패·rate limit·시간 초과·예산 부족은 실행 실패/미완료로 남기고 다른 mode로 전환하지 않는다.

Action의 final message에는 토큰 사용량이 없을 수 있다. 관측하지 못한 사용량·비용은 unknown으로 보고하고 API 프로젝트 사용량 화면에서 확인한다. 정상 PR과 버그 PR의 실제 검증 결과를 self-hosted와 따로 기록한다.

공식 문서: [Codex Action](https://learn.chatgpt.com/docs/github-action), [Action 설정](https://github.com/openai/codex-action/blob/13e9c17417b29e9a276f73ec6ed7fb574137d3c3/action.yml), [API 별도 과금](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform).
