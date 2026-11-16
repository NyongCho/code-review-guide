# Self-hosted Codex 구독 방식

초기 대상은 관리하는 private 저장소다. public 가이드 저장소에 구독 인증 runner를 연결하지 않는다. 이 경로는 서버 운영 비용과 구독 사용 한도를 사용하며, 실패 시 API로 우회하지 않는다.

## 서버 준비

1. Linux에 전용 실행 계정과 작업 디렉터리를 준비한다. 개인 계정의 Codex home·메모리·스킬·후크를 공유하지 않는다.
2. Python 3.11 이상, Git, 고정 Codex CLI를 설치한다. 현재 비교 기준은 CLI 0.169.0이다. 전역 기존 설치를 덮어쓰지 않고 전용 경로를 사용한다.
3. 해당 계정에서 `codex login --help`를 확인하고 지원하는 로그인 방법으로 ChatGPT 구독 인증을 연결한다. 인증 파일을 repo·artifact·로그에 넣지 않는다.
4. [격리 결정 문서](decisions/runtime-isolation.md)에 따라 `review` permission profile과 합성 canary 검사를 준비한다. 모델 본체 인증과 도구의 파일 읽기 권한을 구분한다.

설정 예시에서 `<...>`는 실제 운영 경로로 바꾼다. 이 예시는 경계를 설명하며 모든 운영 probe를 대신하지 않는다.

```toml
default_permissions = "review"
web_search = "disabled"
project_doc_max_bytes = 0

[permissions.review.filesystem]
":minimal" = "read"
"<immutable-input-root>" = "read"
"<pinned-native-codex-binary>" = "read"

[permissions.review.network]
enabled = false
```

MCP·외부 검색·개인 확장 기능은 연결하지 않는다. 각 실행은 새 workspace를 받고 PR 지침 파일은 비활성 자료로 변환한다. 필요한 바이너리와 읽기 root가 실제 고정 버전에서 동작하는지 확인한다.

## GitHub 연결

- runner 등록 전 **허용 저장소 및 workflow/ref 접근 제한**이 계정에서 실제 지원되는지 확인한다. label만으로 접근을 제한했다고 판단하지 않는다.
- 제한을 지원하지 않으면 private 제어 저장소에만 runner를 등록하는 배치를 사용한다. 대상 프로젝트에는 runner·구독 인증을 직접 연결하지 않는다. 보호된 entry에서 dispatch하고 제어 저장소가 PR 정보를 다시 확인한다.
- Actions의 runner 등록 화면에서 제공하는 해당 플랫폼 명령을 사용한다. 등록 token을 문서나 셸 이력에 저장하지 않는다. 기존 runner/서비스 상태를 확인해 중복 등록하지 않는다.
- API 키·publisher token을 서버의 공통 환경에 넣지 않는다. 모델 실행과 테스트·게시의 자격증명을 분리한다.
- 서버 재시작 후 전용 runner 서비스 상태, CLI 버전, 인증 상태, 격리 증거의 일치를 확인한다.

최초 PR에서는 정상·버그·민감 변경과 새 workflow를 이용한 접근 우회를 확인한다. 실제 PR 검증 전 상태는 `needs_verification`이다. 전체 운영 안내와 증거는 개발 완료 시 인계한다.

공식 문서: [Codex 인증](https://learn.chatgpt.com/docs/auth), [비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode), [runner 접근 관리](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access).
