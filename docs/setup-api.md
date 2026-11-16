# GitHub-hosted API 방식

ChatGPT 구독과 API 과금은 별도다. API 프로젝트·모델 접근·검증 예산을 확인한 후 실행한다. key 값은 채팅이나 repo에 넣지 않는다.

공개 저장소도 API mode로 실행할 수 있다. `allowed_actors`에 있는 사람의 같은 저장소 PR만 허용하며 fork PR·미허용 작성자는 모델 호출 전에 거절한다. 보호 환경과 trusted branch 제한은 공개 저장소에서도 필수다.

1. 프로젝트 설정의 mode를 `api`로 명시하고 `api_budget.approved_usd`, `api_budget.max_calls`를 지정한다. 이는 승인된 예산과 호출 제한이며, 공급자 측 강제 비용 상한의 존재를 보장하지 않는다.
2. 보호된 default branch만 접근 가능한 GitHub Environment `review-runtime`을 만든다. 키는 그 환경의 `OPENAI_API_KEY` secret으로 등록한다. feature/PR ref에서 접근이 거절되는지 합성 canary로 확인한다.
3. 공식 `openai/codex-action`을 `13e9c17417b29e9a276f73ec6ed7fb574137d3c3`로 고정하고 CLI 버전·모델·추론 강도도 기록한다. `openai-api-key` 입력만 키를 받으며 저장소 코드 job의 공통 환경에 두지 않는다.
4. 일회성 Linux runner에서 `safety-strategy: drop-sudo`와 읽기 제한 permission profile을 사용한다. `sandbox`와 함께 지정하지 않는다. [격리 검사](decisions/runtime-isolation.md)를 통과하기 전 실제 PR 입력으로 모델을 호출하지 않는다.
5. 생성 결과, 자격증명 없는 테스트, GitHub 게시를 분리한다. Action 실패·rate limit·시간 초과·예산 부족은 실행 실패/미완료로 남기고 다른 mode로 전환하지 않는다.

Action의 final message에는 토큰 사용량이 없을 수 있다. 관측하지 못한 사용량·비용은 unknown으로 보고하고 API 프로젝트 사용량 화면에서 확인한다. 정상 PR과 버그 PR의 실제 검증 결과를 self-hosted와 따로 기록한다.

공식 문서: [Codex Action](https://learn.chatgpt.com/docs/github-action), [Action 설정](https://github.com/openai/codex-action/blob/13e9c17417b29e9a276f73ec6ed7fb574137d3c3/action.yml), [API 별도 과금](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform).

## 필수 runtime 파일과 활성화

설치기는 다음 두 scaffold를 만든다. 둘 다 보호된 main에 있어야 하며 PR에서 바꾼 사본은 사용하지 않는다.

- `.review/runtime/api/config.toml`: `review` profile, 외부 검색 금지, `project_doc_max_bytes=0`, 입력 `/home/runner/review-input`과 **실제 고정 native Codex 실행 파일**의 읽기 권한.
- `.review/runtime/api/isolation.json`: 처음에는 `needs_verification`과 false checks. 실제 canary 결과를 확보한 뒤 원본 증거와 함께 갱신한다.

prepare 단계가 profile을 `/home/runner/review-home/config.toml`로 복사하고 report를 입력 밖에 보관한다. profile의 native 경로는 npm/Node 설치 위치에 따라 달라진다. placeholder를 임의 경로로 바꾸지 말고 사용 중인 CLI/runner에서 실행 가능한지 확인한다. Node/runner 이미지 변경으로 경로가 바뀌면 해당 경로의 canary를 재실행한다.

보고서의 `policy_digest`는 Action 실행 **전** profile 원문의 SHA-256, `codex_version`은 실제 버전, `mode`는 `api`, `runner`는 프로젝트 config의 runner(기본 `linux`)다. `checks`의 네 항목은 모두 실제 검사 결과여야 한다. 공식 Action은 provider/proxy 설정을 추가하므로 실행 후 profile hash와 읽기/네트워크 권한이 유지되는지도 별도 증거로 남긴다.

[공개 합성 canary](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43821487215)는 가짜 키와 빈 prompt로 공식 Action을 초기화하고 파일·쓰기·네트워크·권한·자동 지침을 검사한 실제 예다. 유료 모델 호출은 없다. 해당 artifact의 config/report는 **그 실행 환경의 증거**이며 다른 환경에 status만 복사해서 사용하지 않는다.

검사 후 `.review/config.json`의 `isolation.status`와 `entry_isolation.status`를 `verified`로 갱신한다. 진입 환경/ref 제한과 테스트 컨테이너 격리까지 확인해야 `entry_isolation`을 올릴 수 있다. [전용 검사 게시 App](setup-publisher.md)의 ID·필수 검사 출처·엄격한 최신 branch 요구를 함께 설정한다. 그 다음 환경 secret `OPENAI_API_KEY`를 등록하고 작은 정상 PR부터 명시적으로 실행한다.

OpenAI 프로젝트의 Limits → Spend에서 **Enforce a hard limit**를 설정할 수 있다. 알림만 설정하는 것과 구분한다. 집행 지연으로 소액 초과가 가능하므로 승인 예산보다 낮은 한도와 여유분을 두고, 실제 호출을 직렬로 확인한다. 다른 작업이 함께 쓰는 프로젝트의 총사용량도 포함한다. [공식 비용 제한 안내](https://developers.openai.com/api/docs/guides/spend-limits)
