# 독립 구현 검토와 수정 기록

대상은 baseline `a414671`부터 `14f2a1c`까지다. 대화 컨텍스트를 공유하지 않은 GPT-6 Astra 에이전트가 읽기 전용으로 전체 변경을 검토했다. 107개 테스트는 통과했지만, 추가 재현에서 아래 문제가 발견됐다. 구현자가 한 번의 수정 과정에서 실패 재현→수정→전체 검사로 보완했다. 두 번째 독립 검토를 수행했다고 주장하지 않는다.

| 발견 | 보완 | 회귀 검증 |
| --- | --- | --- |
| 일반 Actions token으로 필수 검사 이름 위조 가능 | 별도 App token을 보호 환경의 entry/finish에서만 발급. 검사 응답의 App ID와 strict branch protection 출처 확인 | 잘못된 App·보호 설정 거절, worker에 token 미전달, 생성 workflow 검사 |
| 같은 SHA의 가변 PR 의도 변경 후 과거 성공 잔존 | merge 의도를 head commit 메시지에 결합. 새 실행 pending, 오래된 동일 head 결과 취소, base/policy는 strict 최신 branch 요구 | PR 본문만으로 승인 의도가 바뀌지 않음, 실제 entry에 커밋 의도·pending 게시, stale base 취소 |
| 서로 다른 reviewer의 ID 충돌이 지적 하나를 소거 | 내용이 다른 같은 ID는 incomplete로 종료 | 버그·권한 문제에 같은 ID를 쓴 뒤 한 건만 기각하는 재현 거절 |
| 평가 manifest에서 모델만 바꿔도 이전 digest 사용 | 구성 내용의 canonical digest와 순서를 검증하고 실행·비교 시 공통 검증 호출 | 세 번째 모델로 바꾼 고정 manifest 거절 |
| 관리 블록 내부의 프로젝트 규칙 소실 | AGENTS/PR template도 기록된 baseline으로 3-way 보존·충돌 처리 | 두 블록 안의 추가 권한 규칙을 재설치 후 보존 |
| API setup의 필수 파일 위치 누락 | 설치기에 미검증 profile/report scaffold 추가, 고정 경로·실측 보고서·활성화 절차 문서화 | 독립 설치에 두 파일 존재, report는 needs_verification |
| 완료 뒤 불필요한 후속 job36개 | terminal 상태에서 남은 tests/inspect를 건너뛰고 finalizer가 마지막 유효 artifact를 선택 | 모든 후속 구간의 terminal 조건 및 actionlint |

마지막 항목은 검토에서 Minor였지만 private Actions 시간·비용에 주는 영향을 고려해 수정 대상으로 올렸다. 자동 수정 커밋에도 원래 변경 목적을 보존하며, 응답 유실 복구 테스트로 재검증했다.

검토자가 판단을 보류한 실제 서버/인증/모델 품질은 [검증 상태](../../validation.md)의 원격 인수 항목으로 유지한다. 초기 언어 지원은 표준 라이브러리 Python이며 다른 언어 지원을 주장하지 않는다. `approved_usd`는 여전히 내부 승인 기록이고, 공급자 비용 제어는 별도로 설정·확인해야 한다.

수정 후 전체 115개 테스트, actionlint, shell syntax, diff whitespace 검사를 통과했다. GitHub App 등록·실제 모델 PR·사람이 확정한 문제집 인수는 아직 완료되지 않았다. 코드 수정 통과와 운영 인수를 구분한다.
