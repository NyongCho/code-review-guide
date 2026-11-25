# Self-hosted Codex 구독 방식

이 방식은 관리하는 **private 저장소**에 사용한다. ChatGPT 구독 사용 한도를 쓰며 실패 시 API로 우회하지 않는다. 공개 저장소의 자동화에는 API 방식을 사용한다. [OpenAI 공식 인증 범위](https://learn.chatgpt.com/docs/non-interactive-mode#authenticate-in-automation)

## 실행 구조

보호된 GitHub-hosted job이 제한된 SSH key로 서버의 `reviewctl serve`만 호출한다. 서버에는 Actions runner나 별도 상주 daemon을 등록하지 않는다. GitHub token과 API key는 서버로 보내지 않는다. PR 테스트는 GitHub-hosted의 별도 컨테이너에서 실행한다.

SSH worker는 서버가 지정한 저장소·모델·CLI 버전만 받아들이고, 고정 작업 디렉터리를 잠금으로 직렬화한다. 요청의 Codex home·격리 보고서 경로는 무시하고 서버 설정을 사용한다. 각 역할은 새 Codex 프로세스로 실행한다.

## 서버 준비

Linux 관리자와 구독 계정 소유자가 다음을 준비한다. 아래 경로는 예시이며 실제 호스트 주소·키를 저장소에 커밋하지 않는다.

1. Python 3.11 이상, Git, OpenSSH server, **bubblewrap**을 설치한다. Debian/Ubuntu에서는 `sudo apt-get install python3 git openssh-server bubblewrap`을 사용한다.
2. `review-worker` 전용 OS 계정을 만들고 sudo·Docker socket·개인 자료 접근 권한을 주지 않는다. `/var/lib/review-worker/work`와 `/var/lib/review-worker/codex-home`은 해당 계정 소유, 0700으로 만든다.
3. 이 guide의 검토한 `runtime/`을 root 소유 `/opt/review-guide/runtime/`에 배치한다. 고정 Codex 실행 파일과 운영 설정도 PR 입력 밖, root가 관리하는 경로에 둔다.
4. Codex 0.169.0의 [공식 Linux release](https://github.com/openai/codex/releases/tag/rust-v0.169.0)를 전용 경로에 설치한다. x86_64 musl tar.gz SHA-256은 `9af4d751fce183faedea629437d5252dbf458eeb04130cf4f97be844621ea985`, native binary SHA-256은 `b452ca20f838a8855a88a41050ee4a694033fff4ea3ecdad5633e6e0e8d13f2b`이다. 기존 전역 CLI는 교체할 필요가 없다.
   같은 릴리스의 `codex-code-mode-host-x86_64-unknown-linux-musl.tar.gz`도 내려받는다. 압축 파일의 SHA-256은 `cbed6a8d25e8268792b757767fbc76d4c62e84bcf8ee4a63f97547f0de3aaceb`이다. 압축을 풀고 실행 파일을 고정 CLI와 같은 디렉터리에 `codex-code-mode-host`라는 이름으로 설치한다(root 소유, 0755). 이 도구가 빠지면 로그인과 버전 확인은 성공해도 모델이 diff를 열 수 없어 리뷰가 `incomplete`로 끝날 수 있다.
5. 해당 계정과 전용 `CODEX_HOME`으로 고정 CLI의 `login --help`를 확인하고 본인이 로그인한다. 개인 auth 파일을 복사하지 않는다. `HOME`도 전용 home으로 지정한다.

Ubuntu 24.04에서 격리 검사가 `bwrap: loopback: Failed RTM_NEWADDR`로 실패하면 커널 로그에서 AppArmor가 `bwrap`을 거절했는지 확인한다. 검증 서버에서는 배포판의 `apparmor-profiles` 패키지가 제공하는 `bwrap-userns-restrict` 프로필로 해결했다. 이 프로필은 호스트의 `/usr/bin/bwrap` 호출에 적용되므로 다른 사용처를 확인하고, 임시 로드 상태에서 전용 계정의 격리 검사를 통과한 뒤 영구 적용한다.

전용 home의 `config.toml` 예시는 다음과 같다. 필요한 바이너리 읽기 경로는 실제 설치 위치와 일치해야 한다.

```toml
default_permissions = "review"
web_search = "disabled"
project_doc_max_bytes = 0

[permissions.review.filesystem]
":minimal" = "read"
"/var/lib/review-worker/work/active-input/workspace" = "read"
"/opt/review-guide/codex/0.169.0/codex" = "read"

[permissions.review.network]
enabled = false
```

전용 home에는 AGENTS·개인 skills·memories·rules·prompts·hooks를 넣지 않는다. `project_doc_max_bytes=0`만으로 전역 AGENTS 로딩이 막히지 않는 것을 실제 probe에서 확인했다. 고정 CLI가 설치하는 `skills/.system`만 허용한다. MCP·외부 검색도 연결하지 않는다.

[격리 검사](decisions/runtime-isolation.md)를 이 계정과 실제 경로에서 실행하고 운영 보고서를 `/etc/review-guide/isolation.json`에 보관한다. 결과 없이 `verified`를 채우지 않는다. 보고서가 준비되면 [server.json 예시](../examples/config/ssh-server.json)의 저장소·모델·경로를 맞춰 `/etc/review-guide/server.json`으로 설치한다.

## SSH와 GitHub 연결

전용 Ed25519 key pair를 만들고 공개키 한 줄에 다음 제한을 붙인다. `authorized_keys`와 상위 디렉터리는 서버 관리자가 관리하고, worker가 제한을 바꾸지 못하게 한다.

```text
restrict,command="/usr/bin/python3 /opt/review-guide/runtime/reviewctl.py serve --server-config /etc/review-guide/server.json" ssh-ed25519 PUBLIC_KEY REVIEW_WORKER
```

`restrict`는 PTY·포워딩·user rc를 막는다. 실행기는 추가 SSH 명령을 거절한다. 호스트 SSH 설정에서도 해당 사용자에 대해 `PermitUserEnvironment no`, forwarding 금지, 불필요한 `AcceptEnv` 금지를 확인한다. 공개키 제한을 우회하는 다른 로그인 방법을 제공하지 않는다.

GitHub Environment `review-runtime`의 배포 branch는 **main만** 허용한다. 변수 `REVIEW_SSH_HOST`, `REVIEW_SSH_PORT`, `REVIEW_SSH_USER`, `REVIEW_SSH_KNOWN_HOSTS`와 secret `REVIEW_SSH_KEY`를 등록한다. 서버 host key는 운영자가 별도 경로로 확인한 값을 사용한다. `ssh-keyscan` 결과를 검증 없이 신뢰하지 않는다. 클라이언트는 strict host checking을 사용하고 agent·사용자 SSH config를 읽지 않는다.

환경에 실제 SSH key를 넣기 전에 합성 값으로 main 진입 성공, PR/feature ref의 기존·신규 workflow 진입 실패를 확인한다. 필수 검사와 branch protection도 실제 머지를 막아야 한다. private 저장소의 보호 기능이 플랜에서 제공되지 않으면 해당 인수 항목은 미완료다.

## 재시작과 청소

상주 worker 재시작 명령은 없다. 다음 SSH 요청이 새 프로세스를 시작한다. `work/worker.lock`은 동시 요청을 직렬화하며 기다리는 시간도 run deadline에 포함된다. 정상 종료·예외·연결 중단 시 만든 input을 제거한다. 강제 종료나 전원 장애로 `active-input`이 남으면 다음 요청은 실행을 거절한다.

운영자가 실행 중인 worker/Codex가 없는지 확인한 뒤 잔여 입력을 조사하고 제거한다. 잠금 파일을 삭제해서 실행 중인 작업을 우회하지 않는다. raw stdout/stderr는 Actions 로그에 출력하지 않으며 실패는 정규화된 상태로 남긴다.
