# 독립 설계 검토 결과

검토일: 2026-11-16

판정: **설계 보완 후 구현 착수 가능.** 최초 검토에서 중복을 합쳐 Important 9건, Minor 1건을 확인했다. 모두 문서에 반영한 뒤 각 검토자에게 재검토를 받았으며, 남은 Critical/Important 설계 지적은 없었다. 실제 코드 품질·보안·실행 성공을 입증하는 판정은 아니다.

## 검토 방법과 범위

세 에이전트를 각각 `fork_turns: "none"`으로 호출했다. 이전 대화와 과거 검토 결과를 공유하지 않고 아래 두 문서, 검토 범위와 읽기 전용 조건만 제공했다. 각자 직접 검토했고 하위 에이전트나 검토자 간 대화를 사용하지 않았다. 수정 후에는 같은 독립 에이전트가 자신의 지적 해결 여부와 새로운 모순을 확인했다.

- [승인된 설계](../specs/2026-11-16-code-review-guide-design.md)
- [구현 계획](../plans/2026-11-16-code-review-guide.md)

| 검토자 | 모델·추론 수준 | 초점 | 재검토 판정 |
| --- | --- | --- | --- |
| independent_structure_review | gpt-6.1-sol / high | 책임 분리, 단순성, 인터페이스, 독립 설치 | 지적 2건 해결, 추가 중요한 문제 없음 |
| independent_execution_review | gpt-6.1-sol / high | 실행 식별, Actions 흐름, 실패·시간 제한, 평가 완전성 | 지적 4건 해결, 추가 중요한 문제 없음 |
| independent_security_review | gpt-6-astra / high | 인증·workflow·지침·승인·평가 정답의 신뢰 경계 | 지적 5건 해결, 실제 인수 조건 유지 |

구조와 실행 검토의 base SHA 지적이 중복되어 고유 지적은 10건이다. 당시 저장소에는 문서만 있고 구현 코드와 Git 이력은 없었다. 따라서 아래 내용은 구현 전 설계 위험과 계약 누락이다.

## 지적과 반영

| ID | 등급 | 실패 조건과 영향 | 반영한 최소 수정 | 재검토 |
| --- | --- | --- | --- | --- |
| R1 | Important | 격리 실패에도 읽기 전용 리뷰가 실행되면 모델 도구가 인증을 읽을 수 있음 | 모든 PR 입력 기반 모델 실행에 격리 gate 적용. 실패 시 호출 0회 검사 | 해결 |
| R2 | Important | PR이 추가한 workflow/job이 entry 검사를 우회해 인증 runner에 진입 | 이벤트/ref/actor/권한 표, runner 접근 제한, 제한 불가 시 제어 저장소 또는 미활성. 새 workflow 우회 검사 | 해결 |
| R3 | Important | PR의 AGENTS.override.md·프로젝트 스킬·설정이 자동 지침으로 로드됨 | trusted CWD와 설정, PR 지침의 비활성 자료 전달, 실제 시작 probe | 해결 |
| R4 | Important | worker가 올바른 사용자명과 digest를 채워 가짜 승인 객체를 만듦 | 원본 사용자 이벤트와 현재 권한 재조회. 정답 확정은 별도 운영자 명령. 위조 승인 거절 검사 | 해결 |
| R5 | Important | 평가 input 밖의 상위 경로·다른 artifact·원본 PR에서 정답을 회수 | input만 있는 worker 경계, 외부 회수 도구별 차단, 실제 도구 접근 거절 확인 | 해결 |
| R6 | Important | head는 같지만 base 또는 PR 의도가 바뀐 실행이 기존 결과와 중복 처리됨 | base/head/input digest를 실행 키에 포함. 게시·복구 때 입력 재확인과 stale_input 처리 | 해결 |
| R7 | Important | 원본 checkout을 지운 뒤 모델 요청이 schema 파일을 찾지 못함 | `.review/schemas/` 설치와 manifest hash. 원본 제거 후 요청 구성·모의 모델 실행까지 독립성 확인 | 해결 |
| R8 | Important | 선택하지 않은 mode나 중간 라운드의 skip이 후속 검사·게시까지 전파됨 | 합류 조건과 선택 결과 규칙 명시. 두 mode의 skip/무수정/중간 종료/실패/취소 검사 | 해결 |
| R9 | Important | 일부 평가 결과가 사라져 성공한 trial만으로 모델 교체 자격을 판정함 | 기대 case/configuration/trial manifest. 누락·중복·미상·미완료·보류는 전체 hold, 분모 고정 | 해결 |
| R10 | Minor | job별 timeout만 설정해 누적 실행이 계획의 60분을 초과함 | 공통 deadline, entry 이후 queue 시간 포함, 남은 시간으로 호출 timeout 축소, 만료 후 호출·push 금지 | 해결 |

책임 분리와 작은 표준 라이브러리 실행 도구, 공통 정책·평가 계약을 유지하는 구조는 적절하다는 평가였다. 전용 서버 애플리케이션이나 범용 모델 SDK 계층을 추가할 필요는 발견하지 못했다. 제어 저장소는 runner 접근 제한을 지원하지 않는 플랫폼의 조건부 배치안이며, 이번에 생성하지 않았다.

## 구현 후 반드시 확인할 조건

1. 고정 CLI/Action에서 합성 canary와 자동 지침 로딩 probe를 통과한 뒤 실제 PR 입력과 인증을 연결한다.
2. 실제 계정에서 새 workflow/job·feature ref가 인증 runner·보호 환경에 접근하지 못함을 확인한다. 기능을 지원하지 않으면 해당 경로를 활성화하지 않는다.
3. 민감 패치·정답 확정 전에 위조 승인 거절, 원본 이벤트·현재 권한·대상 digest 확인을 검증한다.
4. 평가 worker의 상위 정답·다른 실행 자료·원본 PR 접근이 실제로 차단되는지 확인한다.
5. 두 실행 mode 각각에서 최신 SHA 테스트·재리뷰, skip/failure/cancel 합류, trial 누락의 교체 보류를 실제 PR 인수로 검증한다.

코드·테스트·runner·실제 인증·모델 품질은 이번에 검사하지 않았다. 검토자는 서버 접속이나 원격 쓰기를 수행하지 않았고, 조정자는 설계·계획·이 보고서만 변경했다.

## 기술 근거 확인

- GitHub의 dependency는 failed/skipped job 뒤의 작업도 건너뛸 수 있고 timeout은 job/step 단위다. 합류 조건과 공통 deadline이 별도로 필요하다. [GitHub workflow 문법](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- PR workflow의 출처와 privileged entry의 출처는 다르며, 신뢰된 entry에서 PR 코드를 실행하면 권한 경계가 무너진다. [pull_request_target 보안 안내](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
- runner 접근 정책은 실제 계정에서 지원·집행되는 구성을 확인해야 한다. [self-hosted runner 접근 관리](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access)
- Codex permission profile은 파일·명령 접근 범위를 제한하며 legacy sandbox와 함께 사용하지 않는다. 웹 검색·연결 등 다른 도구의 경계도 따로 확인한다. [Codex 권한](https://learn.chatgpt.com/docs/permissions)
- Action의 프로세스 권한 제어와 모델 명령 권한은 별개이고, PR 지침 파일도 신뢰할 수 없는 입력이다. [Codex Action 보안 안내](https://github.com/openai/codex-action/blob/main/docs/security.md)

위 기능의 현행 문서를 확인했지만, 설치할 CLI/Action 버전이나 사용자 계정에서 실제 작동한다고 확인한 것은 아니다.

## 검토 대상 식별

Git 이력이 없는 상태여서 SHA-256으로 문서 revision을 기록한다.

| 문서 | 최초 검토 | 최종 재검토 |
| --- | --- | --- |
| 설계 | `9c2187dfcb75567793e01f4fd4d25af6314cb3942e5745b10183a56176a9536f` | `9ee134588039aa0d7f83be6473c6032bd8e5331f4e152f3f819e30ae575c8bb5` |
| 구현 계획 | `84553df47fb38468efd88381ed962892fc44665263595848046df40182612f66` | `3cfd90bdea91c9e3f5212f87681ed0e6820ad8b97178fbc36c443e55abebe41c` |
