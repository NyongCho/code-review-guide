# Code Review Guide

프로젝트에 AI 코드 리뷰 체계를 설치하고, 경험을 규칙·자동 검사·평가 문제집으로 쌓는 공개용 가이드와 도구다. 설치 후에는 프로젝트가 설정과 자료를 소유하며 원본 guide checkout 없이 동작하도록 구성한다.

**현재 범위:** 로컬 구현·모의 인수 검증 완료. 실제 GitHub PR 운영과 두 실행 경로의 전체 격리 검증은 진행 중이다. 준비되지 않은 실행은 기본적으로 차단한다. 세부 증거는 [검증 상태](docs/validation.md)에 있다.

## 어떤 흐름인가

1. bootstrap 스킬이 테스트·CI·민감 경로·배포 상태를 조사해 7개 방어 계층의 현황과 다음 작업을 만든다.
2. PR마다 bugs/security/verify를 새 세션으로 실행한다. 처음에는 AI 관찰 모드이며 필수 CI와 사람 확인은 별도로 표시한다.
3. 허용한 경우에만 지적 범위 안에서 수정한다. 기본 최대 3회 수정 후에도 새 head의 테스트와 재리뷰가 필요하다. 자동 머지는 하지 않는다.
4. 반복 지적과 사고는 테스트/린트·규칙 변경안·평가 후보로 남긴다. 정답 확정과 모델 교체는 사람이 결정한다.

배포 전 프로젝트는 배포·복구 계층의 적용 조건을 남긴다. 파일이 만들어졌다는 이유로 운영 중이라고 표시하지 않는다. 1인 프로젝트를 독립된 두 사람의 승인 체계라고 주장하지 않는다.

## 시작하기

로컬 도구는 Python 3.11 이상과 Git을 사용하며 외부 Python 패키지가 필요 없다. v1 실행 대상은 private 저장소, 인수 샘플은 표준 라이브러리만 쓰는 Python 프로젝트다. 생성된 테스트 job은 고정한 Python Docker 이미지에서 네트워크·호스트 쓰기·권한 상승을 제한한다. 다른 언어/의존성 설치는 해당 테스트 이미지와 격리를 따로 검증해야 한다.

[bootstrap 스킬](skills/review-bootstrap/SKILL.md)을 구축 에이전트에 제공하고, 다음 중 config 예시를 복사해 저장소·사용자·모델·테스트 명령을 맞춘다.

| 실행 방식 | 설정 예시 | 설치 안내 |
| --- | --- | --- |
| 전용 서버의 Codex 구독 로그인 | [self-hosted.json](examples/config/self-hosted.json) | [서버 설정](docs/setup-self-hosted.md) |
| GitHub-hosted 공식 Codex Action + API 키 | [api.json](examples/config/api.json) | [API 설정](docs/setup-api.md) |

두 방식은 자동 전환하지 않는다. API 예시의 3회 제한은 bugs/security/verify 한 묶음이며 자동 수정까지 하려면 검증 예산 안에서 호출 수를 별도로 정해야 한다. `approved_usd`는 승인한 예산 기록이며 달러 단위 강제 차단기가 아니다. API 모델 접근성은 실제 계정에서 확인한다.

```bash
python3 runtime/reviewctl.py validate --config project-config.json
python3 runtime/reviewctl.py install --target /path/to/project --config project-config.json --dry-run > install-proposal.json
python3 runtime/reviewctl.py install --target /path/to/project --config project-config.json --apply
```

설치 결과에는 `AGENTS.md` 안내, `REVIEW.md`, 프로젝트별 maintain 스킬, `.review/` 실행기·schema·프롬프트·계층 상태, PR/승인/평가 워크플로가 들어간다. 런타임 격리와 GitHub 진입 제한을 실검증하기 전에는 모델을 호출하지 않는다. 생성된 검사 이름과 required checks를 연결하는 설정은 [운영 안내](docs/operations.md)에 정리한다.

## 유지와 모델 변경

평소에는 설치된 `.review/bin/reviewctl.py`와 GitHub 워크플로를 사용한다. [maintain 스킬](skills/review-maintain/SKILL.md)은 첫 배포·인증 도입·마이그레이션·사고·모델 변경 때 점검한다. 템플릿 업데이트는 기존 프로젝트 설정을 입력으로 다시 적용안을 만들며, 로컬 편집은 보존하고 충돌은 `.review/proposals/`에 남긴다.

[문제집과 모델 교체](docs/evaluations.md)는 입력·규칙·도구·rubric을 고정하고 중요 사례를 최소 3회 평가한다. 누락된 실행, 미확정 판정, 중요 퇴행이 있으면 교체를 보류한다. 평균 점수만으로 자동 승격하지 않는다.

## 개발 검증

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_workflows.py
```

두 번째 명령은 checksum으로 고정한 actionlint 개발 도구를 내려받아 생성 워크플로를 검사한다. 모의 인수에서는 실제 Git 객체와 Python 테스트를 사용하고 모델/GitHub는 모의 응답을 사용한다. 모델 품질·실제 서버 격리·Actions 실행 검증을 대신하지 않는다.

[Python 인수 샘플](examples/python-project/) · [설계](docs/superpowers/specs/2026-11-16-code-review-guide-design.md) · [개발 계획](docs/superpowers/plans/2026-11-16-code-review-guide.md)
