# 운영과 업데이트

설치한 프로젝트의 `.review/`가 운영 기준이다. 원본 guide는 업데이트 공급원이며 서비스처럼 계속 띄우지 않는다. 초기에는 `review_mode=observe`, `auto_fix=false`, 격리 상태 `needs_verification`으로 시작한다.

## 활성화 전

1. [사용자 인증 안내](../scripts/setup-access.sh)를 필요한 경우 본인 터미널에서 실행한다. 키는 채팅이나 `.env`로 전달하지 않는다.
2. [서버](setup-self-hosted.md) 또는 [API](setup-api.md) 경로의 실제 계정·버전·읽기/네트워크/권한 상승·지침 발견·보호 환경/ref 제한을 확인한다. 실제 증거 없이 status만 바꾸지 않는다.
3. 선택한 mode의 샘플에서 정상/버그/민감 PR을 실행한다. source snapshot의 base/head/input digest와 게시된 check의 SHA가 맞아야 한다.
4. [전용 게시 App](setup-publisher.md)을 구성하고 `review-guide/ci`, `review-guide/human`을 그 App ID에 묶어 required checks로 연결한다. strict 최신 branch 요구와 관리자 적용도 켠다. AI 차단 전환 후에는 `review-guide/ai`도 연결한다. 실패 check가 실제 머지를 막는지 음성 검사한다. private 저장소에서 필요한 보호 기능을 제공하지 않는 플랜이면 검증 완료로 표시하지 않는다.

AI 관찰 모드의 neutral은 리뷰 성공을 뜻하지 않는다. 댓글에 `incomplete`/`failed`가 있으면 실행 문제다. CI 성공은 같은 head의 컨테이너 검사 결과로만 게시한다. 사람 확인은 위험도에 따라 별도로 판정한다. 1인 프로젝트는 한 명의 확인이며 독립된 두 사람의 승인이 아니다.

## 사람 확인과 AI 차단 전환

댓글의 `human_binding`은 확인할 repo/base/head/input/policy 범위다. 내용을 검토한 다음 **Approve scoped review decision** workflow를 trusted branch에서 실행하고 binding에 해당 JSON을 넣는다. 이후 같은 입력으로 리뷰를 다시 실행한다. 원본 dispatch의 actor/triggering_actor가 사람이고 현재 write/maintain/admin 권한이 있으며 protected workflow의 성공한 binding job과 일치해야 효력이 있다. 댓글을 고치거나 worker JSON에 `approved`를 넣어서는 승인되지 않는다.

모델 차단 전환에는 평가 근거를 확인한 뒤 보호된 설정을 변경하고, 아래 모양의 binding으로 별도 승인을 남긴다. 값을 현재 실행의 실제 기록에서 가져온다.

```json
{"kind":"blocking-policy","policy_sha":"ACTUAL_SHA","config_digest":"ACTUAL_DIGEST","rules":{"REVIEW.md":"ACTUAL_DIGEST"}}
```

정책·정답·workflow 변경이나 기존 테스트 완화는 자동 수정 대상이 아니다. 해당 변경을 별도 PR로 확인한다. 승인 효력은 입력/정책이 바뀌면 다시 확인해야 한다.

## 중단·실패·재시도

| 상태 | 확인과 후속 작업 |
| --- | --- |
| 인증 만료 | 전용 계정에서 고정 CLI의 `login --help`와 `login status` 지원을 확인한 뒤 본인이 다시 로그인한다. 개인 auth 파일을 복사하지 않는다. |
| 구독 한도/API 오류 | 해당 경로에서 실패로 남긴다. 한도/모델 접근을 확인하고 같은 mode로 다시 실행한다. 자동 과금 우회는 없다. |
| timeout / deadline | `deadline_at`과 실제 시작/queue 시간을 확인한다. 이미 만료한 실행은 새 모델 호출·push를 하지 않는다. 현재 입력으로 새 실행을 시작한다. |
| stale_head / stale_input | 최신 PR의 base/head 또는 저장소 입력이 바뀐 것이므로 과거 결과를 재사용하지 않는다. 현재 PR 입력으로 다시 실행한다. |
| push 후 응답 유실 | publisher가 parent와 예상 patch tree를 재조회한다. 다른 head를 덮어쓰지 않는다. 사람이 force-push로 복구하지 않는다. |
| artifact 누락/보존 만료 | 출처/run/attempt/digest가 검증되지 않는 자료로 복구하지 않는다. 현재 입력으로 새 실행을 만들고 이전 실행은 미완료로 남긴다. |
| 중요 지적 지속/3회 한도 | `needs_human`의 근거와 패치 범위를 확인한다. 마지막 수정도 tests+fresh review를 생략하지 않는다. |

GitHub Actions 화면에서 실행/attempt를 확인하거나 인증된 운영자 터미널에서 다음 명령을 사용한다.

```bash
gh run list --repo OWNER/PRIVATE_PROJECT --workflow review-entry.yml
gh run view RUN_ID --repo OWNER/PRIVATE_PROJECT
gh run download RUN_ID --repo OWNER/PRIVATE_PROJECT --dir evidence/RUN_ID
```

직접 내려받은 artifact는 조사 자료다. 실행기는 API가 제공한 원본 SHA-256과 run/head/name을 확인하고 경로 탈출·symlink·과대 압축을 거절한 뒤 사용한다. 실행 중단을 조사할 때 모델 raw 로그보다 정규화된 result/state/publication을 먼저 본다.

재실행은 전체 workflow를 새 attempt로 실행한다. 현재 v1의 artifact 이름은 attempt에 묶여 있으므로, 실패 job만 재실행해 이전 attempt의 중간 자료가 자동으로 이어진다고 가정하지 않는다. 실패 job 재실행만 필요한 운영은 실제 인수 후 별도 지원 범위로 정한다.

## 서버 재시작과 동시성

구독 방식은 [제한된 SSH worker](setup-self-hosted.md)를 사용한다. 서버에 Actions runner 서비스는 없다. 재시작 뒤 전용 계정·고정 CLI·Codex home·보고서와 host key를 확인한다. 모델 계정에는 Docker socket이나 publisher 자격증명을 주지 않는다.

PR별 concurrency가 이전 실행을 취소한다. 서버는 단일 `worker.lock`으로 요청을 직렬화한다. `active-input`이 남아 있으면 자동으로 덮어쓰거나 지우지 않고 거절한다. 운영자가 실행 중인 작업이 없는지 확인한 후 잔여 입력을 조사·청소한다. 연결 중단 시 모델 프로세스도 종료하도록 했으나 실제 서버의 SSH disconnect/재부팅 검증은 아직 필요하다.

## 예산·보존·업데이트

`api_budget.max_calls`는 한 실행에서 시작할 모델 호출 수다. `approved_usd`는 합의 기록이며 공급자의 달러 단위 강제 상한이 아니다. 각 실제 인수 호출 전 사용량을 확인하고 남은 승인 예산을 산정한다. 사용량 미관측은 unknown으로 두고 API 프로젝트에서 대조한다. 사용자가 승인한 전체 실검증 예산을 각 재실행마다 새 예산처럼 초기화하지 않는다.

기본 artifact 보존은 14일이다. 정답으로 확정할 후보만 [평가 절차](evaluations.md)로 장기 보관한다. 키·auth 파일·운영자 서명 key·원본 private 로그를 public guide로 옮기지 않는다.

업데이트 전에 프로젝트 branch를 만들고 현재 `.review/config.json`을 설치 입력으로 사용한다.

```bash
python3 /path/to/new-guide/runtime/reviewctl.py install \
  --target /path/to/project --config /path/to/project/.review/config.json --dry-run > update-proposal.json
```

제안된 변경과 충돌을 검토하고 적용한 뒤 생성 workflow와 프로젝트 테스트를 검사한다. `max_rounds` 변경은 DAG 재생성이 필요하다. runtime/profile/CLI가 바뀌면 격리 증거를 새로 만들고 모델 변경이면 고정 문제집 비교를 다시 수행한다. rollback은 검증된 이전 설치 commit과 당시 CLI/profile을 함께 되돌린다. 기존 model의 인증이 실패했다고 다른 과금 경로를 활성화하지 않는다.

첫 배포 전에는 `.review/layers.json`의 6·7번을 다시 검토한다. 실제 통합 검사, 기능 차단/롤백 명령, 감지 지표·연락 담당과 rehearsal 증거가 생겨야 상태를 갱신한다. 사고 후에는 어느 계층이 잡았어야 했는지 기록하고 재현 가능한 회귀 검사와 사례 후보를 만든다.

OpenAI 프로젝트의 Limits → Spend에서 **Enforce a hard limit**를 설정할 수 있다. 알림만 설정하는 것과 구분한다. 집행 지연으로 소액 초과가 가능하므로 승인 예산보다 낮은 한도와 여유분을 두고, 실제 호출을 직렬로 확인한다. 다른 작업이 함께 쓰는 프로젝트의 총사용량도 포함한다. [공식 비용 제한 안내](https://developers.openai.com/api/docs/guides/spend-limits)

수정 모델은 파일마다 저장소 기준 경로, 작업(`create`, `replace`, `delete`), 수정 후 전체 내용을 반환한다. 삭제 시 내용은 빈 문자열이다. 실행기는 리뷰한 커밋으로 임시 Git 인덱스를 만들고 파일 형식과 허용 경로를 확인한다. Git이 만든 diff를 원래 트리에 다시 적용해 제안된 트리와 일치할 때만 게시한다. 테스트 디렉터리와 일반적인 테스트 파일명(예: `src/test_total.py`, `src/total.test.ts`)의 기존 파일은 사람이 검토한다. 프로젝트 고유 테스트 이름이나 경로는 `sensitive_paths`에 등록해 보호한다. 새 커밋에는 테스트와 버그·보안·최종 리뷰가 다시 필요하다.

잘못된 응답 형식이나 Git 공백 오류는 같은 커밋에서 한 번 재작성을 요청한다. 이 호출과 수정 후 리뷰 3회가 남은 예산에 들어가야 한다. 두 번째 형식 오류나 허용 범위 밖의 변경은 사람에게 넘긴다. 자체 서버 방식은 프로젝트의 설치본과 서버의 `/opt/review-guide/runtime/`을 같은 버전으로 업데이트한다.
