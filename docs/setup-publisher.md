# 필수 검사 게시용 GitHub App

필수 검사의 이름만 보호하면 PR이 추가한 workflow가 같은 이름으로 성공을 게시할 수 있다. 이 실행기는 별도 GitHub App으로 `review-guide/ci`, `review-guide/human`, `review-guide/ai`를 게시하고, branch protection이 **그 App ID**를 요구하는지 실행 전 확인한다. 일반 `GITHUB_TOKEN`에는 checks write를 주지 않는다.

## 한 번 설정하기

1. [GitHub App 등록](https://github.com/settings/apps/new)에서 본인 계정용 App을 만든다. homepage는 프로젝트 URL, webhook은 비활성화한다. Repository permissions는 **Checks: Read and write**, **Contents: Read-only**, **Administration: Read-only**다. Metadata read는 기본 권한이다. 다른 계정에 설치할 필요는 없다.
2. 해당 App을 검증할 저장소에만 설치한다. App ID를 기록한 뒤 [개인 계정의 GitHub Apps](https://github.com/settings/apps) → 해당 App의 **Edit → Credentials → Key pairs → New key**에서 `.pem` 파일을 내려받는다. 이것이 App의 private key다. 키는 채팅·저장소에 넣지 않는다. [현재 GitHub 안내](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps)
3. GitHub Environment `review-publisher`를 만들고 deployment branch는 trusted branch(기본 main)만 허용한다. 그 환경의 variable `REVIEW_APP_ID`와 secret `REVIEW_APP_PRIVATE_KEY`를 등록한다. 모델의 `review-runtime` 환경과 분리한다.
4. 프로젝트 `.review/config.json`에 숫자 `check_publisher_app_id`를 설정한다. 이 값과 환경의 App ID가 같아야 한다. 원격 보호 설정도 아래 계약으로 맞춘다.

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [],
    "checks": [
      {"context": "review-guide/ci", "app_id": 123456},
      {"context": "review-guide/human", "app_id": 123456}
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

`123456`은 실제 ID로 바꾼다. 일반 GitHub Actions App이나 모든 출처를 뜻하는 값은 사용하지 않는다. AI 차단 정책을 활성화하면 같은 App의 `review-guide/ai`도 필수 목록에 추가한다. 키를 넣기 전 main 외 ref 접근 거절을 합성 값으로 검사하고, 새 PR workflow가 같은 check 이름을 위조해도 App 출처가 달라 머지하지 못하는지 실제로 검사한다.

생성 workflow의 entry/finish만 보호 환경에서 단기 installation token을 발급한다. 공식 `actions/create-github-app-token`은 commit `fee1f7d63c2ff003460e3d139729b119787bc349`로 고정하며 job 종료 시 token을 폐기한다. App key/token은 모델·테스트 job이나 artifact에 전달하지 않는다.

## 무엇을 승인하는가

GitHub의 required check는 commit SHA와 App 출처에 연결되며 PR 제목·설명 변경을 원자적으로 감지하지 않는다. 따라서 **변경 의도는 head commit 메시지에 기록**한다. PR의 수정 가능한 제목·설명은 참고 정보이며 merge 승인 계약에 포함하지 않는다. 의도 변경은 새 커밋으로 남긴다.

새 trusted entry는 검사를 진행 중으로 게시한다. 오래된 같은 head 결과는 해당 실행의 검사만 취소하고, 새 실행의 성공을 덮어쓰지 않는다. branch protection의 strict 최신화 요구가 base/policy 변경 후 기존 head로 머지하는 것을 막는다. 이 요구를 끄면 운영 지원 조건을 벗어나며 실행기는 시작을 거절한다. 취소된 작업이 finalizer까지 실행되지 못해도 진행 중인 필수 검사는 성공으로 바뀌지 않는다.

App key 회전은 새 key를 환경 secret에 등록하고 합성 검사를 확인한 뒤 이전 key를 폐기한다. App 설치 해제·권한 변경·ID 불일치는 실행 실패로 남긴다.

토큰 발급에서 `Invalid keyData`가 나오면 Secret에 `.pem` 파일명·지문 대신 **파일 전체 내용**을 넣었는지 확인한다. BEGIN/END 줄을 포함하고 줄바꿈을 보존한다. 고정한 Action은 RSA PKCS#1·PKCS#8을 처리하므로 정상 키를 임의로 변환할 필요는 없다. Secret은 등록 후 값을 읽을 수 없으며 수정 저장 후 다시 실행해 확인한다.

공식 근거: [GitHub App 등록](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app), [App token Action](https://github.com/actions/create-github-app-token), [branch protection API](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection).
