# 실행 격리의 확인 범위

모든 PR 입력 기반 모델 실행은 운영자가 준비한 runtime 설정과 격리 증거를 확인한 뒤 시작한다. raw worker 출력이나 프로젝트 PR이 만든 `verified` 값은 인증 근거가 아니다. 실행기는 보호된 revision에서 불러온 config를 사용하며, 운영 증거는 PR workspace 밖에 둔다.

## 선택한 방식

- self-hosted: 보호된 GitHub-hosted job에서 제한된 SSH forced command를 호출한다. 전용 OS 계정의 Codex home, 고정 CLI, 명시적인 `review` permission profile을 사용한다. 모델 도구는 input과 최소 실행 파일만 읽는다. 구독 인증은 Codex 본체가 사용하고 도구에서 읽을 수 없어야 한다. 빌드·테스트와 publisher는 별도 실행 경계다.
- API: 공식 Codex Action을 commit `13e9c17417b29e9a276f73ec6ed7fb574137d3c3`로 고정한다. API 키는 Action 입력에만 전달하고 `drop-sudo`와 읽기 제한 profile을 함께 사용한다. 이 전략은 일회성 GitHub-hosted runner용이며 개인 서버에 실행하지 않는다.
- fixer도 파일 쓰기 권한 없이 패치만 반환한다. 적용은 deterministic scope 검사와 publisher가 담당한다.
- legacy `sandbox` 입력과 permission profile은 함께 설정하지 않는다.

## 실제로 확인한 것

2026-11-16 로컬 Codex 0.169.0의 `codex help sandbox`에서 `sandbox -P <profile> -C <directory> -- <command>` 형식을 확인했다. 자격증명 없는 임시 설정으로 합성 canary probe를 실행했다.

| 항목 | 결과 |
| --- | --- |
| 허용한 input 파일 읽기 | 성공 |
| input 밖의 합성 canary 파일 읽기 | 거절 |
| input 디렉터리 파일 쓰기 | 거절 |
| 로컬 네트워크 | 외부 TCP 연결 EPERM으로 거절 |
| 로컬 권한 상승 | setuid(0) 거절, NoNewPrivs=1, effective capabilities=0 |
| PR 자동 지침 | debug prompt-input에서 inert canary가 로딩되지 않음 |
| Codex home의 전역 지침 | AGENTS.override.md는 로딩됨; 실행기가 별도로 거절하도록 보완 |
| 실제 서버 | 같은 native 버전의 sandbox는 bubblewrap 부재로 실패. 임시 파일 제거, 전역 CLI/개인 인증 유지 |
| 실제 PR·구독 인증·API 경로 | 미검증 |

최초 probe는 native executable 경로를 허용하지 않아 sandbox 내부 실행에 실패했다. 최소 OS 경로와 고정 native 실행 파일 경로를 읽기 허용한 다음 파일 경계 검사가 통과했다. 이후 네트워크·권한 상승·지침 probe를 추가했다. 임시 파일은 제거했고 실제 인증이나 API 호출을 사용하지 않았다. 이 결과로 runtime 전체를 `verified`로 올리지 않는다.

## 구독 worker의 실제 검증 (2026-11-25)

Ubuntu 24.04의 전용 계정에서 Codex 0.169.0과 배포판의 bubblewrap 프로필을 사용했다. 격리 안에서 합성 입력 읽기는 성공했고, 입력 밖 파일 읽기와 작업 디렉터리 쓰기 및 네트워크 연결은 거절됐다. 실행 프로세스에서 `NoNewPrivs=1`, 유효 capability 0, 일반 사용자 UID를 확인했다. 프로젝트 지침에 넣은 표식도 모델 입력에 나타나지 않았다.

제한된 SSH 키로 합성 변경을 전달하자 구독 모델이 `sum(set(items))`에서 중복 가격이 누락되는 결함을 지적했다. 검증자가 추가한 회귀 테스트에서 입력 `[100, 100]`의 기대값 200과 실제값 100이 달랐다. 합산을 수정한 뒤 샘플 테스트 3개가 모두 통과했고 같은 모델의 재리뷰 결과는 `verified`(지적 0건)였다. 이 실행은 서버의 리뷰 경로를 검증했다.

같은 결함 커밋으로 비공개 샘플에 초안 PR을 열자 `pull_request_target` 이벤트가 `entry` 작업을 시작했다. 게시용 App을 설정하지 않은 환경에서 토큰 발급이 `appId option is required`로 실패했고, 후속 작업 76개는 건너뛰었다. 별도로 기본 브랜치 보호 API를 조회했을 때 GitHub는 현재 플랜에서 HTTP 403을 반환했다. PR에서 worker 호출과 필수 검사에 의한 머지 차단은 미검증 상태다.

## 운영 활성화 증거

격리 보고서는 `status`, `policy_digest`(전용 config.toml의 SHA-256), `codex_version`, `mode`, `runner`, `checks`를 기록한다. `checks`는 secret_read_denied / network_denied / instructions_inert / privilege_escalation_denied 각각의 실제 검사 결과다. 단순 파일 수정으로 true를 채우는 절차는 운영 검증이 아니다. 실제 도구 권한으로 읽기·네트워크·권한 상승·시작 지침을 검사하고 원본 증거를 연결한다.

설정·버전·runner가 바뀌면 증거를 재생성한다. 보고서 자체는 모델 workspace에 전달하지 않는다. 운영자가 제공한 보호된 설정을 검증하는 기능과, 실제 환경의 안전성을 입증하는 과정은 별개다.

공식 근거: [Codex permission profile](https://learn.chatgpt.com/docs/permissions), [Action 보안](https://github.com/openai/codex-action/blob/13e9c17417b29e9a276f73ec6ed7fb574137d3c3/docs/security.md).
