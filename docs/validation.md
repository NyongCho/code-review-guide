# 검증 상태

2026-11-16 기준. 파일 설치, 로컬 계약 검사, 실제 모델 호출, 운영 인수는 서로 다른 증거다. 이 문서는 실제 수행한 범위를 기록한다.

| 범위 | 결과 | 증거와 한계 |
| --- | --- | --- |
| 독립 설치/업데이트 | 로컬 통과 | source bundle 없는 실행, 사용자 규칙 보존, 3-way 충돌 및 실패 롤백 |
| 상태·정책·GitHub 경계 | 로컬 통과 | stale base/head/의도, 정확한 패치 tree, 중복 게시/커밋 복구, 승인 원본·권한, zip 경로·digest |
| 유한 PR/평가 DAG | 정적 검사 통과 | 두 mode의 선택 분기, 수정 후 명시적 검사, actionlint1.7.12; 실제 Actions 미검증 |
| 합성 Python 인수 | 두 mode 모의 통과 | 실제 Git·Python 테스트 + 가짜 모델/GitHub, 설치→버그→수정·회귀 테스트→새 head 재리뷰→사례→교체 보류 |
| 평가 정답·판정 | 로컬 통과 | 입력 snapshot 검증, 후보만 자동 생성, 별도 운영자 확정, 서명 변조 거절, 고정 분모·중요 누락 보류 |
| Codex 구독 smoke | 제한적 실제 성공 | 전용 임시 0.169.0/gpt-6-astra 호출만 확인. 전체 리뷰/서버 운영 증거가 아님 |
| Codex 파일 권한 canary | 제한적 로컬 성공 | 0.169.0에서 입력 읽기, 외부 파일 읽기 거절, 쓰기 거절. 네트워크/권한 상승/지침 로딩과 실제 서버는 별도 검증 필요 |
| 전용 self-hosted runner 진입 제한 | needs_verification | 보호된 workflow/ref 밖에서 인증 runner를 호출하지 못하는지 확인 필요 |
| API 실제 모델 호출 | needs_verification | 전체 검증 예산 US$5 승인. 키 연결 및 호출 전; 사용 비용 0 |
| 정상/버그/민감 실제 PR | needs_verification | 별도 private 샘플의 원격 PR/head/run/check 증거 필요 |
| 실제 반복 평가·사람 정답 | needs_verification | 합성 판정 fixture를 실제 사용자의 정답 승인으로 취급하지 않음 |
| 배포·운영 복구 | pending_applicability | 첫 배포 전 기능 차단/롤백/감지 근거를 프로젝트별로 확보 |

## 재현 명령

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_acceptance -v
python3 scripts/check_workflows.py
```

격리 보고서를 흉내 낸 테스트 fixture는 파서와 흐름을 검사하기 위한 자료다. 배포 설정에서 같은 값을 복사해 `verified`로 바꾸면 안 된다. 실제 self-hosted/API 각각의 합성 canary와 진입 제한 검증이 먼저다.

## 실제 운영 인수에서 남길 증거

각 mode마다 pinned CLI/Action/모델/effort, runtime profile hash, runner/ref 제한, 테스트 컨테이너 canary, PR 번호·base/head·input digest, 테스트/리뷰/check/수정 commit, 실패와 복구 결과를 private 샘플에 기록한다. 공개 guide에는 호스트 주소·개인 경로·키·private 코드·원본 로그를 제외한 결과만 남긴다.

설계 §10의 완료 조건과 실제 경로별 결과 매핑은 서버/API 인수 후 갱신한다. 한 경로만 검증되었다면 다른 경로를 지원 완료로 표시하지 않는다.
