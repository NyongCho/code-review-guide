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
| Codex 파일 권한 canary | 제한적 로컬 성공 | 0.169.0에서 파일·네트워크·권한 상승 거절. 전역 AGENTS 로딩 위험을 발견하여 실행 전 거절. 실제 서버는 bubblewrap 부재로 실패 |
| 제한된 SSH worker | 로컬 통과 / 실제 서버 needs_verification | 서버 소유 경로·allowlist·버전·deadline·zip 거절, forced-command CLI와 가짜 SSH 종단간 검사. 실제 전용 계정·bubblewrap·키 연결 필요 |
| GitHub 보호 환경 | 합성 원격 통과 | main dispatch 성공, PR의 기존·신규 workflow 거절. 실제 key는 미등록 |
| Branch protection | 공개 샘플 음성 인수 통과 | private는 Pro 요구403. 공개 샘플의 strict·관리자 적용·전용 App 출처 필수 설정. 실패 ci 및 잘못된 App의 같은 이름 성공 검사로 exact-head 머지 시도 시405 거절 |
| API 공식 Action 격리 | 합성 원격 통과 | pinned0.169.0, fake key/no prompt. 파일·쓰기·네트워크·root 승격·시작 지침·외부 프로세스 환경/메모리 canary 통과. 실제 모델·키 호출과 구분 |
| 설치된 테스트 컨테이너 | 합성 원격 통과 | 실제 `test_command`로 호스트·home·Docker socket·환경변수·네트워크·쓰기·UID·capabilities·메모리·프로세스 제한 확인. 모델 호출 없음 |
| 전용 게시 App | 부분 검증 | App ID·보호 Secret 등록, 위조 check 거절 통과. 실제 토큰 발급은 Invalid keyData로 실패하여 키 재등록 대기; App 게시 성공은 아직 미확인 |
| API 실제 모델 호출 | needs_verification | 전체 검증 예산 US$5 승인. 키 연결 및 호출 전; 사용 비용 0 |
| 정상/버그/민감 실제 PR | needs_verification | 구독 private / API public 샘플의 원격 PR/head/run/check 증거 필요 |
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

각 mode마다 pinned CLI/Action/모델/effort, runtime profile hash, 보호 환경/ref 제한, 테스트 컨테이너 canary, PR 번호·base/head·input digest, 테스트/리뷰/check/수정 commit, 실패와 복구 결과를 private 샘플에 기록한다. 공개 guide에는 호스트 주소·개인 경로·키·private 코드·원본 로그를 제외한 결과만 남긴다.

## 설계 §10 완료 조건 매핑

아래의 모의 통과는 두 mode를 대상으로 한 로컬 증거다. 실제 모델을 포함하는 인수는 아직 완료되지 않았다.

| 조건 | 도구/로컬 증거 | 구독 실제 인수 | API 실제 인수 |
| --- | --- | --- | --- |
| 1 설치·사용자 편집 보존 | install 테스트·스킬 행동 검사 통과 | pending | pending |
| 2 정상 PR·오탐 | acceptance 모의 통과 | pending | pending |
| 3 버그 지적·별도 검증 | acceptance 모의 통과 | pending | pending |
| 4 수정·회귀 검사·재리뷰 | 실제 Git/Python + 모의 모델 통과 | pending | pending |
| 5 민감 변경 사람 확인 | policy/lifecycle 테스트 통과 | pending | pending |
| 6 중복·stale·상한·실패 | lifecycle/GitHub/adapter 테스트 통과 | pending | pending |
| 7 후보·사람 정답 | 후보와 서명 경계 통과, 실제 정답 미확정 | pending | pending |
| 8 동일 문제집·중요 퇴행 보류 | evaluate/eval_runtime 모의 통과 | pending | pending |
| 9 수정 후 명시적 CI | 생성 DAG + acceptance 모의 통과 | pending | pending |
| 10 설치·운영 안내 | 두 mode와 SSH 예시 작성 | 서버 선행 조건 미충족 | 키·격리 인수 전 |
| 11 계약·개선 자료 보존 | 공통 실행기·3-way 설치 통과 | pending | pending |
| 12 과금 fallback 금지 | adapter 실패/모드 검사 통과 | pending | pending |

공개 API 샘플은 [code-review-guide-sample](https://github.com/NyongCho/code-review-guide-sample)이다. 구독 경로는 공개 저장소에서 실행하지 않는다. 환경의 [main 성공](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43818243935)과 [새 PR workflow 차단](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43818354472)은 합성 canary이며 실제 모델 품질·키 격리의 증거가 아니다. 차단 annotation은 `refs/pull/1/merge`가 review-runtime 배포 규칙에 허용되지 않음을 명시한다.

한 경로만 검증되었다면 다른 경로를 지원 완료로 표시하지 않는다.

독립 전체 코드 검토에서 중요한 문제6개와 낭비되는 후속 job을 발견해 보완했다. 가변 PR 설명 대신 커밋 메시지를 승인 의도로 사용하며, 필수 검사는 별도 App ID·strict branch 보호에 묶는다. 원격 App 인수가 끝나기 전 운영 완료로 표시하지 않는다.

추가 증거: [게시 환경 main 성공](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43822772399), [게시 환경 PR 차단](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43822653001), [프로세스 경계까지 포함한 API 합성 격리](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43822775874). [독립 구현 검토와 수정](superpowers/reviews/2026-11-16-code-review.md).

[샘플 PR6](https://github.com/NyongCho/code-review-guide-sample/pull/6)에 guide `940587c`를 설치했고, [테스트 컨테이너 canary](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43824609484)의 12개 검사를 통과했다. 진입·모델 설정은 여전히 `needs_verification`이며 실제 모델 호출은 비활성이다. `review-approval`은 main만 허용하고 본인의 명시적 확인을 요구하도록 설정했다. 1인 확인을 독립된 두 사람의 승인으로 간주하지 않는다.

[위조 검사 PR7](https://github.com/NyongCho/code-review-guide-sample/pull/7)에서 일반 GitHub Actions App이 `review-guide/ci`·`review-guide/human` 성공을 게시했지만, GitHub는 지정된 App 출처가 아니라며 해당 head의 머지를 HTTP405로 거절했다. [전용 App 토큰 발급 실행](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43825112981)은 키 파싱에 실패했다. 키가 실제로 유효하다는 증거로 Secret 이름의 존재만 사용하지 않는다.
