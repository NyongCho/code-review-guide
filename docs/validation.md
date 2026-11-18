# 검증 상태

2026-11-18 기준. 파일 설치, 로컬 계약 검사, 실제 모델 호출, 운영 인수는 서로 다른 증거다. 이 문서는 실제 수행한 범위를 기록한다.

| 범위 | 결과 | 증거와 한계 |
| --- | --- | --- |
| 독립 설치/업데이트 | 로컬 통과 | source bundle 없는 실행, 사용자 규칙 보존, 3-way 충돌 및 실패 롤백 |
| 상태·정책·GitHub 경계 | 로컬 통과 | stale base/head/의도, 정확한 패치 tree, 중복 게시/커밋 복구, 승인 원본·권한, zip 경로·digest |
| 유한 PR/평가 DAG | 정적·정상 PR 원격 통과 | 두 mode의 선택 분기와 actionlint1.7.12. 정상 API PR은 3역할 종료 후 미사용 후속 job 생략. 수정 루프·평가 원격은 검증 중 |
| 합성 Python 인수 | 두 mode 모의 통과 | 실제 Git·Python 테스트 + 가짜 모델/GitHub, 설치→버그→수정·회귀 테스트→새 head 재리뷰→사례→교체 보류 |
| 평가 정답·판정 | 로컬 통과 | 입력 snapshot 검증, 후보만 자동 생성, 별도 운영자 확정, 서명 변조 거절, 고정 분모·중요 누락 보류 |
| Codex 구독 smoke | 제한적 실제 성공 | 전용 임시 0.169.0/gpt-6-astra 호출만 확인. 전체 리뷰/서버 운영 증거가 아님 |
| Codex 파일 권한 canary | 제한적 로컬 성공 | 0.169.0에서 파일·네트워크·권한 상승 거절. 전역 AGENTS 로딩 위험을 발견하여 실행 전 거절. 실제 서버는 bubblewrap 부재로 실패 |
| 제한된 SSH worker | 로컬 통과 / 실제 서버 needs_verification | 서버 소유 경로·allowlist·버전·deadline·zip 거절, forced-command CLI와 가짜 SSH 종단간 검사. 실제 전용 계정·bubblewrap·키 연결 필요 |
| GitHub 보호 환경 | 합성 원격 통과 | main dispatch 성공, PR의 기존·신규 workflow 거절. 보호 환경에 실제 API/App key 등록 후 호출·게시 확인 |
| Branch protection | 공개 샘플 음성 인수 통과 | private는 Pro 요구403. 공개 샘플의 strict·관리자 적용·전용 App 출처 필수 설정. 실패 ci 및 잘못된 App의 같은 이름 성공 검사로 exact-head 머지 시도 시405 거절 |
| API 공식 Action 격리 | 합성 원격 통과 | pinned0.169.0, fake key/no prompt. 파일·쓰기·네트워크·root 승격·시작 지침·외부 프로세스 환경/메모리 canary 통과. 실제 모델·키 호출과 구분 |
| 설치된 테스트 컨테이너 | 합성 원격 통과 | 실제 `test_command`로 호스트·home·Docker socket·환경변수·네트워크·쓰기·UID·capabilities·메모리·프로세스 제한 확인. 모델 호출 없음 |
| 전용 게시 App | 합성 원격 통과 | 키 재등록 후 인증·토큰 폐기·진행 중 검사·최종 CI/사람/AI 검사·댓글 게시 성공. 위조 성공 검사와 실제 사람 확인 실패를 구분하여 머지 거절 |
| API 실제 모델 호출 | 제한적 실제 통과 | Codex0.169.0/gpt-6-luna/low, 고정 prompt 응답 검증. 입력10057·출력15 토큰 관측, 보수적 표준 요금 추정 약US$0.0013. 전체 예산US$5; 공급자 hard limit은 미확인. 리뷰 품질 검증과 구분 |
| 정상/버그/민감 실제 PR | API 정상·버그 검출 확인 / 자동 수정 검증 중 | PR12의 bugs/security/verify 지적0, 같은 head의 실제 테스트·App 검사 통과 후 보호 설정 유지하여 머지. PR13에서 버그 확인. 운영자 복구 커밋의 테스트·재리뷰 통과. PR17은 자동 수정 커밋 게시까지 확인했다. 같은 실행에서의 수정 후 재리뷰·민감 PR·구독 경로는 미완료 |
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
| 2 정상 PR·오탐 | acceptance 모의 통과 | pending | PR12 정상 사례 1건 지적0 |
| 3 버그 지적·별도 검증 | acceptance 모의 통과 | pending | PR13 재실행에서 중복 금액 버그를 검출하고 별도 검증자가 확정 |
| 4 수정·회귀 검사·재리뷰 | 실제 Git/Python + 모의 모델 통과 | pending | PR13 모델 작성 패치를 운영자가 보정·게시한 뒤 통과. 자동 게시 미검증 |
| 5 민감 변경 사람 확인 | policy/lifecycle 테스트 통과 | pending | pending |
| 6 중복·stale·상한·실패 | lifecycle/GitHub/adapter 테스트 통과 | pending | pending |
| 7 후보·사람 정답 | 후보와 서명 경계 통과, 실제 정답 미확정 | pending | pending |
| 8 동일 문제집·중요 퇴행 보류 | evaluate/eval_runtime 모의 통과 | pending | pending |
| 9 수정 후 명시적 CI | 생성 DAG + acceptance 모의 통과 | pending | pending |
| 10 설치·운영 안내 | 두 mode와 SSH 예시 작성 | 서버 선행 조건 미충족 | 키·격리·정상 PR 인수 확인 |
| 11 계약·개선 자료 보존 | 공통 실행기·3-way 설치 통과 | pending | pending |
| 12 과금 fallback 금지 | adapter 실패/모드 검사 통과 | pending | pending |

공개 API 샘플은 [code-review-guide-sample](https://github.com/NyongCho/code-review-guide-sample)이다. 구독 경로는 공개 저장소에서 실행하지 않는다. 환경의 [main 성공](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43818243935)과 [새 PR workflow 차단](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43818354472)은 합성 canary이며 실제 모델 품질·키 격리의 증거가 아니다. 차단 annotation은 `refs/pull/1/merge`가 review-runtime 배포 규칙에 허용되지 않음을 명시한다.

한 경로만 검증되었다면 다른 경로를 지원 완료로 표시하지 않는다.

독립 전체 코드 검토에서 중요한 문제6개와 낭비되는 후속 job을 발견해 보완했다. 가변 PR 설명 대신 커밋 메시지를 승인 의도로 사용하며, 필수 검사는 별도 App ID·strict branch 보호에 묶는다. 원격 App 인수가 끝나기 전 운영 완료로 표시하지 않는다.

추가 증거: [게시 환경 main 성공](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43822772399), [게시 환경 PR 차단](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43822653001), [프로세스 경계까지 포함한 API 합성 격리](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43822775874). [독립 구현 검토와 수정](superpowers/reviews/2026-11-16-code-review.md).

[샘플 PR6](https://github.com/NyongCho/code-review-guide-sample/pull/6)에 guide `940587c`를 설치했고, [테스트 컨테이너 canary](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43824609484)의 12개 검사를 통과했다. 당시 진입·모델 설정은 `needs_verification`이며 실제 모델 호출은 비활성이었다. 후속 PR10·11에서 별도 검증과 승인 후 활성화했다. `review-approval`은 main만 허용하고 본인의 명시적 확인을 요구하도록 설정했다. 1인 확인을 독립된 두 사람의 승인으로 간주하지 않는다.

[위조 검사 PR7](https://github.com/NyongCho/code-review-guide-sample/pull/7)에서 일반 GitHub Actions App이 `review-guide/ci`·`review-guide/human` 성공을 게시했지만, GitHub는 지정된 App 출처가 아니라며 해당 head의 머지를 HTTP405로 거절했다. [전용 App 토큰 발급 실행](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43825112981)은 키 파싱에 실패했다. 키가 실제로 유효하다는 증거로 Secret 이름의 존재만 사용하지 않는다.

키 재등록 후 실제 연동에서 발견한 두 오류를 수정했다. 진행 중 검사 요청의 `conclusion:null`은 GitHub가422로 거절하여 필드를 생략하며, artifact의 PR event SHA와 보호된 workflow SHA를 별도로 검증한다. [완료한 제어 흐름](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43827168365)은 실제 컨테이너 테스트 성공, 모델 호출0, App의 CI success·human failure·AI neutral 및 댓글을 게시했다. 같은 head의 위조 human success가 있어도 머지는405로 거절되었다. 이 결과는 AI 리뷰 품질의 증거가 아니다.

[범위가 지정된 사람 승인](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43828021730) 후 [새 실행](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43881207526)의 필수 CI·human이 성공하여 PR10을 보호 설정 변경 없이 머지했다. 오래된 workflow 재실행의 시간 기준은 `created_at` 대신 `run_started_at`을 쓰도록 수정했다.

[첫 API 연결 검사](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43881747910)는 공식 Action이 자동으로 넣는 `--skip-git-repo-check`를 다시 전달하여 CLI가 추론 전에 중단됐다. [수정 PR11](https://github.com/NyongCho/code-review-guide-sample/pull/11)은 중복 옵션을 제거하고 JSON 사용량 이벤트와 재실행 시간 수정을 포함한다. 해당 실패 실행들은 추론에 진입하지 않았다.

2026-11-18: 사용자가 PR11의 정확한 커밋을 승인하고 GitHub 처리를 위임했다. [승인 작업](https://github.com/NyongCho/code-review-guide-sample/actions/runs/43882595231)과 [필수 검사](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44217228690) 후 보호 설정 변경 없이 머지했다. [수정된 연결 검사](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44217576459)에서 `{"ok":true}`와 완료 usage event를 확보했다. 표준 [모델 요금](https://developers.openai.com/api/docs/models/gpt-6-luna)에 따라 입력 전체를 cache-write 단가로 잡은 보수적 추정은 US$0.001264625이며 실제 청구서 확인은 아니다. [정상 PR12](https://github.com/NyongCho/code-review-guide-sample/pull/12)의 [실제 리뷰](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44217789445)는 bugs/security/verify의 새 세션 3회, 지적0, `status=verified`로 완료됐다. 테스트·검토 head가 `c231abfe3ee049424daf7cffb837424c1ae4974a`로 일치했고, 전용 App의 CI·human 성공 후 보호 설정 변경 없이 머지했다. 3회 리뷰 사용량까지 포함한 누적 보수 추정은 US$0.023324375다. 이 한 사례는 일반적인 오탐률을 입증하지 않는다.

[버그 PR13의 첫 실행](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44218701877)은 두 리뷰어가 중복 금액 누락을 지적했으나, 같은 ID에 다른 설명을 써서 `incomplete`로 중단했다. 자동 수정 성공으로 계산하지 않는다. 지적을 각각 보존하여 검증자가 모두 처리하게 하는 수정과, 사례 export에서 커밋 목적이 빠지는 수정을 [PR14](https://github.com/NyongCho/code-review-guide-sample/pull/14)로 준비했다. 관련 회귀 테스트의 실패→성공과 전체119개 통과를 확인했으며, 이후 보호된 승인 절차로 샘플에 적용했다. 정상·버그 사례 입력은 정답 미확정 후보로 보존했다.

[PR14의 실제 리뷰](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44219446925)는 동일 head `bdb2eb4f1fd1dbb297af0e6993748708f648a1a8`에 테스트와 세 역할 리뷰를 완료하고 지적0·`verified`를 기록했다. 사람 승인 후 같은 커밋에서 필수 검사를 통과하고 샘플 main에 병합했다(`321e6448`). 이 실행까지 관측한 API 비용의 누적 보수 추정은 US$0.087634625이며, 실제 청구액은 미확인이다.

[PR13 재검증](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44225933427)에서 첫 시도는 두 리뷰어가 각각 낸 F1을 별도 ID로 보존하고 검증자에게 전달했다. 검증자는 두 ID를 확정하고 최종 지적에는 하나만 남겨 실행기가 수정을 보류했다. 같은 커밋의 두 번째 시도에서는 검증자가 한 건을 확정했고 수정 모델은 중복 금액을 복원하는 패치를 생성했다. 새 회귀 테스트는 생성하지 않았다. 게시기의 임시 clone에서 얕게 가져온 PR 커밋을 찾지 못해 원격 커밋과 재리뷰 단계는 실행되지 않았다.

실제 모델 패치를 임시 저장소에 적용해 기존 테스트 두 개와 중복 입력 합계 400을 확인했다. [게시기 수정 PR15](https://github.com/NyongCho/code-review-guide-sample/pull/15)는 임시 저장소로 현재 PR 커밋을 직접 가져오고, 검증자와 수정자에게 중복 지적 처리와 새 테스트의 허용 범위를 알려준다. GitHub와 같은 shallow fetch 조건에서 게시 오류를 재현한 뒤 전체 119개 테스트를 통과했다.

PR15는 사람 승인과 필수 CI를 통과해 샘플 main에 병합됐다(`7848699`). 해당 리뷰는 얕은 체크아웃에서 브랜치 이름 없이 커밋을 가져올 수 있는지 지적했다. 실제 PR 커밋이 FETCH_HEAD에만 있는 조건에서 패치 적용 결과가 기대 트리와 일치함을 확인했다. 이 PR의 AI 수정 단계는 출력 형식 오류로 끝났다.

[PR13 자동 수정 시도](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44236011590)에서 모델은 합계 수정과 회귀 테스트를 작성했다. 첫 패치는 작업 디렉터리 접두사와 잘못된 hunk 줄 수를 포함해 거절됐다. 재실행은 응답 상태가 `findings`인데 지적 목록이 비어 있어 거절됐다. 운영자가 첫 패치의 경로와 줄 수를 바로잡았다. 새 테스트는 원래 코드에서 100과 200의 차이로 실패했고 수정을 적용한 뒤 세 테스트 모두 통과했다. [복구 커밋](https://github.com/NyongCho/code-review-guide-sample/commit/b5acf915ce18c29975b389f38a9d239c640243af)은 운영자가 게시했다.

[복구 커밋 재검증](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44237646781)에서 테스트와 버그·보안·최종 검증이 같은 커밋 `b5acf91`에 대해 통과했다. 최종 상태는 `verified`, 지적은 0건이었다. 이 실행까지의 API 사용량 기준 누적 보수 추정은 US$0.3696다.

PR13은 검증한 복구 커밋으로 병합됐다(`9665c88`). main과의 최종 차이는 중복 금액 회귀 테스트 한 개다. 이후 두 형식 오류를 실행 기록에서 재생해 재작성 1회, 반복 실패 시 보류, 이미 검증한 올바른 패치를 입력했을 때 게시 단계 진입을 로컬에서 확인했다. 모델이 스스로 올바른 재작성을 생성해 원격 커밋을 게시하는 과정은 별도 검증 대상으로 남아 있다.

[샘플 PR16](https://github.com/NyongCho/code-review-guide-sample/pull/16)은 커밋 `8d8391f`에 대한 승인과 세 필수 검사 통과 후 `9e418b2`로 병합됐다. 로컬 Git 2.53과 GitHub 러너의 Git 2.56에서 잘못된 diff의 진단 문구가 달라 형식 오류 분류를 수정했고, [가이드 CI의 122개 테스트](https://github.com/NyongCho/code-review-guide/actions/runs/44239426489)가 통과했다. [샘플 AI 리뷰](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44239506203)는 새 커밋에서 형식 재작성을 다시 허용할지 지적했고 보호 경로라 `needs_human`으로 끝났다. 첫 재작성 후 생성된 새 커밋에서 다시 오류를 내는 입력을 재생했다. 실행 전체에서 재작성 한 번을 소비한 뒤 사람에게 넘기는 것이 운영 규칙과 일치해 이 동작을 유지했다.

[샘플 PR17](https://github.com/NyongCho/code-review-guide-sample/pull/17)은 기존 테스트 세 개를 통과하지만 음수 크레딧을 합계에서 누락하는 변경을 사용했다. [첫 실행](https://github.com/NyongCho/code-review-guide-sample/actions/runs/44240929686)에서 모델이 버그를 확인하고 첫 제안으로 소스를 수정했다. [자동 커밋](https://github.com/NyongCho/code-review-guide-sample/commit/bec60a44b94451d6f42e8d3b9d260a138e00eb98)은 새 테스트를 포함하지 않았다. 같은 실행의 게시 직후 PR head 확인은 `stale_head`로 끝났고 수정 후 테스트와 재리뷰는 건너뛰었다. 수정 커밋에서 기존 테스트 세 개와 크레딧 예시(500 − 125 = 375)를 별도로 확인했다.
